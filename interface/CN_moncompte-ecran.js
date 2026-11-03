// ═════════════════════════════════════════════════════════════════
// TITRE      : Mon compte : les six pages de l'écran personnel (vue d'ensemble, profil, branchements, notifications, sécurité, droits et données)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #b78d06
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine « Mon compte » : la fiche calquée sur celle de Dolibarr (avec son portrait), les branchements que les modules déclarent, la matrice de notifications, la sécurité (mot de passe, clés, sessions, appareils, journal) et mes droits.
// MÉTHODE    : une scène du module comptes (CASS.monCompte, appelée par CN_comptes-ecran.js pour les écrans mc_*) ; chaque page lit les capacités du noyau (comptes.*, webauthn.*, notifications.*, dolibarr.*, droits.*) et n'écrit que par elles. Dolibarr est facultatif : sans son module, rien n'en est dit.
// ═════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=b78d06 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };
  const jeton = () => { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } };
  const quand = (t) => { try { return new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };
  const PAGES = { mc_accueil: "accueil", mc_profil: "profil", mc_liens: "liens", mc_alertes: "alertes", mc_secu: "secu", mc_donnees: "donnees" };
  const ALLER = (p) => () => { if (CASS.ouvrirEcran) CASS.ouvrirEcran("comptes:" + p, { mc_accueil: "Vue d'ensemble", mc_profil: "Profil et affichage", mc_liens: "Mes branchements", mc_alertes: "Notifications", mc_secu: "Sécurité et sessions", mc_donnees: "Mes droits et mes données" }[p]); };
  const CIVILITES = [["", "—"], ["MR", "M."], ["MME", "Mme"], ["MLE", "Mlle"], ["DR", "Dr"]];
  const GENRES = [["", "—"], ["man", "Homme"], ["woman", "Femme"], ["other", "Autre"]];
  const LANGUES = [["fr_FR", "Français"], ["en_US", "English"], ["es_ES", "Español"], ["de_DE", "Deutsch"], ["it_IT", "Italiano"], ["pt_PT", "Português"], ["nl_NL", "Nederlands"]];
  const NIVEAUX = [["critique", "Critique", "ce qui ne peut pas attendre : réveille"], ["avoir", "À voir", "attend la fin des heures calmes"], ["info", "Information", "rien d'urgent : la cloche suffit"]];
  const CANAUX = [["cloche", "Cloche"], ["mail", "Courriel"], ["telegram", "Telegram"], ["webhook", "Webhook"]];

  const CSS = ".mc .row{display:flex;gap:12px;align-items:center;justify-content:space-between;padding:9px 0;border-top:1px solid var(--line);flex-wrap:wrap}.mc .row:first-child{border-top:0}" +
    ".mc .row .t{min-width:0;flex:1 1 220px}.mc .row .t small{display:block;color:var(--txt-faint);font-size:12px}.mc .lead{margin:6px 0 0;color:var(--txt-soft);max-width:68ch}.mc h3 small{font-weight:400;color:var(--txt-faint)}" +
    ".mc .sub{color:var(--txt-faint);font-size:12.5px;margin:0 0 12px}.mc .f{display:block;font:650 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);margin:0 0 4px}" +
    ".mc .f code{font:500 10px 'JetBrains Mono',monospace;text-transform:none;letter-spacing:0;color:var(--txt-faint);opacity:.8}.mc.sans-doli .f code{display:none}" +
    ".mc textarea{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:7px 10px;width:100%;min-height:64px;resize:vertical}" +
    ".mc .todo{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}.mc .todo:first-of-type{border-top:0}.mc .todo .t{flex:1;min-width:0}.mc .todo small{display:block;color:var(--txt-faint)}" +
    ".mc .tg{position:relative;width:38px;height:22px;border-radius:99px;border:0;background:var(--line-strong,#cbd2da);padding:0;flex:none}.mc .tg:after{content:'';position:absolute;left:3px;top:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:left .15s}.mc .tg.on{background:var(--accent)}.mc .tg.on:after{left:19px}.mc .tg[disabled]{opacity:.5}" +
    ".mc .grille3{display:grid;grid-template-columns:minmax(150px,1.4fr) repeat(3,minmax(70px,1fr));gap:6px 10px;align-items:center}.mc .grille3 .c{text-align:center}.mc .grille3 .h{font:650 10.5px 'Inter',sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint)}" +
    ".mc .savebar{position:sticky;bottom:10px;display:none;gap:12px;align-items:center;flex-wrap:wrap;background:var(--txt);color:var(--bg);border-radius:14px;padding:9px 14px;z-index:5}.mc .savebar.on{display:flex}.mc .savebar .grow{flex:1}.mc .savebar .cu-btn{color:var(--txt)}" +
    ".mc .err{color:var(--danger);font-size:12.5px;margin:6px 0 0}.mc .ok{color:var(--ok)}.mc .mono{font-family:'JetBrains Mono',monospace;font-size:12px}.mc .codes{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px;margin:8px 0;font:600 13px 'JetBrains Mono',monospace}.mc .codes span{border:1px dashed var(--line-strong,var(--line));border-radius:8px;padding:5px 8px;text-align:center}" +
    ".mc .portrait{width:84px;height:84px;border-radius:50%;object-fit:cover;flex:none;border:1px solid var(--line)}.mc .cmp{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:var(--surface);margin-top:10px}" +
    "@media (max-width:760px){.mc .grille3{grid-template-columns:minmax(110px,1.4fr) repeat(3,minmax(54px,1fr))}}";

  const ico = (d) => '<svg class="cu-i" viewBox="0 0 24 24"><path d="' + d + '"/></svg>';
  const b64u = (s) => { s = (s || "").replace(/-/g, "+").replace(/_/g, "/"); const b = atob(s + "=".repeat((4 - s.length % 4) % 4)); const o = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; };
  const versB64u = (buf) => { let s = ""; const o = new Uint8Array(buf); for (let i = 0; i < o.length; i++) s += String.fromCharCode(o[i]); return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); };
  const chip = (t, c) => '<span class="cu-chip ' + (c || "") + '">' + esc(t) + "</span>";
  const portraitHtml = (p, grand) => p && p.present ? '<img class="portrait" alt="" src="data:' + esc(p.type) + ";base64," + esc(p.base64) + '">' : '<span class="cu-av' + (grand ? " big" : "") + '">' + esc((p && p.initiales) || "?") + "</span>";
  const select = (champ, options, valeur) => '<select data-champ="' + champ + '">' + options.map((o) => '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(valeur || "") ? " selected" : "") + ">" + esc(o[1]) + "</option>").join("") + "</select>";
  const entree = (champ, etiquette, valeur, type, plus) => '<div><label class="f">' + etiquette + ' <code>' + champ + '</code></label><input type="' + (type || "text") + '" data-champ="' + champ + '" value="' + esc(valeur) + '"' + (plus || "") + "></div>";
  const reseauxEnTexte = (j) => { try { return Object.entries(JSON.parse(j || "{}")).map(([k, v]) => k + ": " + v).join("\n"); } catch (e) { return ""; } };
  const reseauxEnJson = (t) => { const o = {}; String(t || "").split("\n").forEach((l) => { const i = l.indexOf(":"); if (i > 0 && l.slice(i + 1).trim()) o[l.slice(0, i).trim()] = l.slice(i + 1).trim(); }); return Object.keys(o).length ? JSON.stringify(o) : ""; };

  CASS.monCompte = async function (corps, ctx) {
    if (!document.getElementById("cu-css") && CASS.comptesCSS) { const st = document.createElement("style"); st.id = "cu-css"; st.textContent = CASS.comptesCSS; document.head.appendChild(st); }
    if (!document.getElementById("mc-css")) { const st = document.createElement("style"); st.id = "mc-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "cu mc"; corps.appendChild(racine);
    const S = { page: PAGES[String(ctx && ctx.ecran || "").split(":")[1]] || "accueil", dolibarr: "absent" };
    const $ = (s) => racine.querySelector(s);
    const $$ = (s) => Array.prototype.slice.call(racine.querySelectorAll(s));
    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { const r = await agir(cap, args); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(e.message || String(e), "err"); return false; } }
    const tete = (t, lead) => "<div><h1>" + esc(t) + '</h1><p class="lead">' + esc(lead) + "</p></div>";

    // ── Dolibarr est facultatif : absent (rien n'en est dit), installé sans lien, relié ──
    async function etatDolibarr() {
      try {
        const r = await agir("dolibarr.fiche_lire", {});
        S.doli = r || { lie: false }; S.dolibarr = r && r.lie ? "lie" : (r && r.configure === false ? "installe" : "non_lie");
      } catch (e) {
        S.doli = null;
        S.dolibarr = /inconnue|module/i.test(String(e.message)) && !/pont|configur|clé|cle/i.test(String(e.message)) ? "absent" : "installe";
      }
      racine.classList.toggle("sans-doli", S.dolibarr === "absent");
    }

    // ═════════ vue d'ensemble ═════════
    async function pAccueil() {
      const [moi, portrait, cles, sess, droits, journal] = await Promise.all([lire("comptes.moi"), lire("comptes.portrait"), lire("webauthn.etat"), lire("comptes.mes_sessions", { courant: jeton() }),
        lire("droits.mes_droits_a_moi"), lire("comptes.mon_journal", { limite: 5 })]);
      const f = (moi && moi.fiche) || {};
      const nbCles = cles ? (cles.cles || []).length : 0, nbSess = sess ? (sess.sessions || []).length : 0, nbDroits = droits ? (droits.droits || []).length : 0;
      const afaire = [];
      if (cles && cles.disponible !== false && nbCles < 2) afaire.push(["w", nbCles ? "Ajouter une seconde clé de sécurité" : "Poser une clé de sécurité", nbCles ? "Si la première est perdue, vous ne pouvez plus entrer." : "Votre mot de passe est aujourd'hui votre seul verrou.", "webauthn", "Ajouter", "mc_secu"]);
      if (moi && !f.lastname) afaire.push(["i", "Compléter ma fiche", "Votre nom n'est pas renseigné : il s'affiche partout où l'on vous nomme.", "comptes", "Compléter", "mc_profil"]);
      if (S.dolibarr === "non_lie") afaire.push(["i", "Relier ma fiche à Dolibarr", "Dolibarr est installé : le lien se confirme une fois, puis il est gardé.", "dolibarr", "Voir", "mc_profil"]);
      return tete("Bonjour " + ((moi && (f.firstname || moi.nom_affiche)) || ""), "Une seule page pour savoir où en est votre compte : ce qui est protégé, ce qui attend une décision, et ce qui s'est passé.") +
        '<div class="cu-carte"><div class="cu-hero">' + portraitHtml(portrait, true) + '<div class="cu-m"><h2>' + esc((moi && moi.nom_affiche) || "") + "</h2><p style=\"margin:2px 0 0;color:var(--txt-soft)\">" + esc([f.job, moi && moi.societe_nom].filter(Boolean).join(" · ")) + "</p>" +
        '<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">' + (moi && moi.admin ? chip("Administrateur", "acc") : "") + chip("Compte actif", "ok") + "</div></div>" +
        '<button class="cu-btn" data-a="aller" data-p="mc_profil">Modifier mon profil</button></div>' +
        '<div class="cu-kpis" style="margin-top:14px"><div class="cu-kpi ' + (nbCles ? "ok" : "warn") + '"><b>' + nbCles + '</b><span>clé(s) de sécurité</span></div><div class="cu-kpi"><b>' + nbSess + '</b><span>session(s) ouverte(s)</span></div><div class="cu-kpi"><b>' + nbDroits + "</b><span>droit(s) détenu(s)</span></div></div></div>" +
        '<div class="cu-carte"><h3>À faire sur mon compte</h3>' + (afaire.length ? afaire.map((a) => '<div class="todo"><div class="t"><b>' + esc(a[1]) + "</b><small>" + esc(a[2]) + ' <span class="cu-why">signalé par ' + esc(a[3]) + '</span></small></div><button class="cu-btn sm' + (a[0] === "w" ? " pri" : "") + '" data-a="aller" data-p="' + a[5] + '">' + esc(a[4]) + "</button></div>").join("") : '<div class="cu-vide">Rien n\'attend votre décision.</div>') + "</div>" +
        '<div class="cu-carte"><h3>Dernière activité sur mon compte</h3>' + ((journal && journal.evenements || []).length ? '<ul class="cu-tl">' + journal.evenements.map((e) => "<li><time>" + esc(quand(e.ts)) + "</time><span>" + esc(e.texte) + (e.ip ? " · " + esc(e.ip) : "") + "</span></li>").join("") + "</ul>" : '<div class="cu-vide">Rien encore.</div>') +
        '<p class="sub" style="margin:8px 0 0">Le journal complet est dans <button class="cu-btn sm" data-a="aller" data-p="mc_secu">Sécurité</button></p></div>';
    }

    // ═════════ profil ═════════
    async function pProfil() {
      const [moi, portrait] = await Promise.all([lire("comptes.moi"), lire("comptes.portrait", { detail: true })]);
      if (!moi || !moi.fiche) return tete("Profil et affichage", "") + '<div class="cu-note">' + esc(S.erreur || "Ce compte n'a pas de fiche : un agent ou un compte système n'en a pas.") + "</div>";
      S.moi = moi; S.fiche = moi.fiche; S.portrait = portrait;
      let cmp = null;
      if (S.dolibarr === "lie") cmp = await lire("dolibarr.fiche_comparer");
      S.cmp = cmp;
      const f = moi.fiche, v = (k) => f[k] || "";
      const sources = [["propre", "Mon image"], ["dolibarr", "Dolibarr"], ["fastpanel", "FastPanel"], ["telegram", "Telegram"], ["initiales", "Mes initiales"]];
      const dispo = (portrait && portrait.disponibles) || {};
      const cartePortrait = '<div class="cu-carte"><h3>Mon portrait</h3><p class="sub">Il vit avec le compte, jamais dans la base d\'un autre produit. Une image que vous téléversez n\'est jamais écrasée par une source externe.</p>' +
        '<div class="cu-hero">' + portraitHtml(portrait, true) + '<div class="cu-m"><div class="row" style="border:0;padding:0"><div class="t"><b>Source</b><small>Affichée : ' + esc((portrait && portrait.source) || "initiales") + "</small></div>" +
        '<select data-a="source" style="max-width:220px">' + sources.filter((s) => s[0] !== "dolibarr" || S.dolibarr !== "absent").map((s) => '<option value="' + s[0] + '"' + ((portrait && portrait.demandee || "") === s[0] ? " selected" : "") + ">" + esc(s[1]) + (s[0] !== "initiales" && !dispo[s[0]] ? " (aucune image)" : "") + "</option>").join("") + "</select></div>" +
        '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><label class="cu-btn sm" style="cursor:pointer">Téléverser une image<input type="file" id="mc-fichier" accept="image/png,image/jpeg,image/webp" hidden></label>' +
        (dispo.propre ? '<button class="cu-btn sm dng" data-a="portrait-retirer">Retirer mon image</button>' : "") + "</div><p class=\"sub\" style=\"margin:8px 0 0\">PNG, JPEG ou WebP · recadrée en carré de 256 px avant l'envoi.</p></div></div></div>";
      const carteDoli = S.dolibarr === "absent" ? "" : S.dolibarr === "installe" ? '<div class="cu-carte"><h3>Dolibarr est installé, mais pas relié</h3><p class="sub">Ma fiche reste complète et utilisable ; le lien apparaîtra dès que l\'administrateur aura posé la clé de mandat (Branchements › Dolibarr).</p></div>' :
        S.dolibarr === "non_lie" ? '<div class="cu-carte"><h3>Lien avec ma fiche Dolibarr</h3><p class="sub">Le login Dolibarr est libre : le lien ne se devine pas, il se confirme une fois. Tant qu\'il n\'est pas confirmé, rien n\'est lu ni écrit.</p><div id="mc-cand"><button class="cu-btn" data-a="chercher">Chercher mon utilisateur Dolibarr</button></div></div>' :
        '<div class="cu-carte"><h3>Ma fiche Dolibarr ' + chip("lié · utilisateur n° " + S.doli.id_doli + " · login " + (S.doli.login || ""), "ok") + '</h3><p class="sub">Mêmes champs, mêmes noms : ma fiche Cassandra et ma fiche Dolibarr se superposent champ à champ.</p>' +
        (cmp && cmp.differents && cmp.differents.length ? '<div class="cmp"><b>' + cmp.differents.length + " écart(s)</b>" + cmp.champs.filter((x) => !x.identique).map((x) => '<div class="row"><div class="t"><code>' + esc(x.champ) + "</code> Cassandra « " + esc(x.cassandra || "(vide)") + " » ≠ Dolibarr « " + esc(x.dolibarr || "(vide)") + ' »</div><span><button class="cu-btn sm" data-a="envoyer" data-c="' + esc(x.champ) + '">Envoyer</button> <button class="cu-btn sm" data-a="reprendre" data-c="' + esc(x.champ) + '">Reprendre</button></span></div>').join("") + "</div>" : '<div class="cu-note" style="margin-top:8px">Les deux fiches disent la même chose.</div>') +
        (cmp && cmp.change_depuis_le_lien ? '<p class="sub" style="margin:8px 0 0">Dolibarr a changé depuis le dernier échange.</p>' : "") +
        '<div style="margin-top:10px"><button class="cu-btn sm dng" data-a="delier">Délier</button></div></div>';
      return tete("Profil et affichage", "Qui je suis pour les autres, et comment l'interface se présente à moi. Rien d'autre ici.") + cartePortrait + carteDoli +
        '<div class="cu-carte"><h3>Identité</h3><div class="cu-g2">' + '<div><label class="f">Civilité <code>civility_code</code></label>' + select("civility_code", CIVILITES, v("civility_code")) + "</div>" + '<div><label class="f">Genre <code>gender</code></label>' + select("gender", GENRES, v("gender")) + "</div>" +
        entree("lastname", "Nom", v("lastname"), "text", ' maxlength="50"') + entree("firstname", "Prénom", v("firstname"), "text", ' maxlength="50"') + '<div><label class="f">Identifiant de connexion <code>login</code></label><input type="text" value="' + esc(moi.compte) + '" disabled></div>' + entree("birth", "Date de naissance", v("birth"), "date") +
        entree("job", "Fonction", v("job"), "text", ' maxlength="128"') + '<div><label class="f">Salarié <code>employee</code></label>' + select("employee", [["0", "Non"], ["1", "Oui"]], v("employee")) + "</div>" + entree("ref_employee", "Référence employé", v("ref_employee"), "text", ' maxlength="50"') +
        entree("dateemployment", "Entrée en fonction", v("dateemployment"), "date") + entree("dateemploymentend", "Sortie de fonction", v("dateemploymentend"), "date") + "</div>" +
        '<p class="sub" style="margin:12px 0 0">Longueurs identiques à celles de Dolibarr (nom et prénom 50, fonction 128, téléphones 30, code postal 25, adresse 255) : un champ trop long est refusé, jamais tronqué en silence.</p></div>' +
        '<div class="cu-g2"><div class="cu-carte"><h3>Coordonnées</h3><p class="sub">Vues par mes collègues et utilisées en signature.</p><div style="display:grid;gap:10px">' +
        entree("email", "Courriel professionnel", v("email"), "email", ' maxlength="255"') + entree("personal_email", "Courriel personnel", v("personal_email"), "email", ' maxlength="255"') + entree("office_phone", "Téléphone professionnel", v("office_phone"), "text", ' maxlength="30"') +
        entree("user_mobile", "Mobile professionnel", v("user_mobile"), "text", ' maxlength="30"') + entree("personal_mobile", "Mobile personnel", v("personal_mobile"), "text", ' maxlength="30"') + entree("office_fax", "Fax", v("office_fax"), "text", ' maxlength="30"') + "</div></div>" +
        '<div class="cu-carte"><h3>Adresse</h3><div style="display:grid;gap:10px">' + entree("address", "Adresse", v("address"), "text", ' maxlength="255"') + entree("zip", "Code postal", v("zip"), "text", ' maxlength="25"') + entree("town", "Ville", v("town"), "text", ' maxlength="50"') +
        entree("country_code", "Pays (code à deux lettres)", v("country_code"), "text", ' maxlength="2" placeholder="FR"') + entree("state_code", "Département", v("state_code"), "text", ' maxlength="10"') + "</div></div></div>" +
        '<div class="cu-carte"><h3>Présentation</h3><div class="cu-g2"><div><label class="f">Langue <code>lang</code></label>' + select("lang", LANGUES, v("lang")) + "</div>" +
        '<div><label class="f">Couleur de la fiche <code>color</code></label><input type="color" data-champ="color" value="#' + esc(v("color") || "0a726b") + '" style="padding:2px;height:36px"></div>' +
        '<div><label class="f">Fuseau horaire <small>propre à Cassandra</small></label><input type="text" data-champ="tz" list="mc-tz" value="' + esc(v("tz")) + '" placeholder="' + esc((() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return ""; } })()) + '"><datalist id="mc-tz">' + ((typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : []).map((z) => '<option value="' + esc(z) + '">').join("")) + "</datalist></div></div>" +
        '<div style="margin-top:10px"><label class="f">Signature <code>signature</code></label><textarea data-champ="signature">' + esc(v("signature")) + '</textarea></div><div style="margin-top:10px"><label class="f">Réseaux sociaux <code>socialnetworks</code> <small>un par ligne : réseau: identifiant</small></label><textarea data-champ="socialnetworks">' + esc(reseauxEnTexte(v("socialnetworks"))) + "</textarea></div>" +
        '<div style="margin-top:10px"><label class="f">Note publique <code>note_public</code></label><textarea data-champ="note_public">' + esc(v("note_public")) + "</textarea></div></div>" +
        '<div class="savebar" id="mc-barre"><span class="grow" id="mc-n"></span><button class="cu-btn" data-a="annuler">Annuler</button><button class="cu-btn pri" data-a="enregistrer">Enregistrer</button></div><div class="err" id="mc-err"></div>';
    }

    // ═════════ branchements : ce que les modules déclarent, affiché par le noyau ═════════
    async function pLiens() {
      const U = CASS.modulesUi;
      if (!U) return tete("Mes branchements", "") + '<div class="cu-note">Le catalogue des modules n\'est pas chargé.</div>';
      try { await U.lire(); } catch (e) { return tete("Mes branchements", "") + '<div class="cu-note">' + esc(e.message) + "</div>"; }
      const mes = U.reglages().filter((r) => r.portee === "compte");
      const parModule = {}; mes.forEach((r) => (parModule[r.module] = parModule[r.module] || []).push(r));
      const mods = Object.keys(parModule).sort();
      S.mods = mods;
      const mir = await lire("canaux.miroir");                       // le miroir Telegram : ce que je dis à Cassandra sur Telegram se répète ici (absent sans le module des canaux)
      const carteMiroir = mir ? '<div class="cu-carte"><h3>Miroir Telegram</h3><div class="row"><div class="t"><b>Répéter mes échanges Telegram dans Cassandra</b><small>Éteint par défaut : rien ne sort de Telegram sans que vous l’ayez demandé.</small></div><button class="tg' + (mir.miroir ? " on" : "") + '" data-a="miroir"></button></div></div>' : "";
      return tete("Mes branchements", "Chaque module déclare ses réglages de portée « compte » dans son manifeste ; le noyau les affiche ici, tous sur la même carte. Les secrets restent dans mon coffre.") + carteMiroir +
        (mods.length ? mods.map((m) => '<div class="cu-carte" data-mod="' + esc(m) + '"><h3>' + esc(U.nomDe(m)) + " <small>" + parModule[m].length + " réglage(s)</small></h3>" + parModule[m].map((r) => U.champ(r)).join("") + "</div>").join("") : '<div class="cu-carte"><div class="cu-vide">Aucun module ne vous laisse de réglage personnel.</div></div>');
    }

    // ═════════ notifications ═════════
    async function pAlertes() {
      const p = await lire("notifications.politique");
      if (!p) return tete("Notifications", "") + '<div class="cu-note">' + esc(S.erreur || "Le module des notifications ne répond pas.") + "</div>";
      S.pol = p;
      const canal = (c) => (p.canaux && p.canaux[c] && p.canaux[c].declare) || c === "cloche";
      const navigateur = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return ""; } })();
      return tete("Notifications", "Une seule matrice : pour chaque gravité, par où je veux être prévenu. La cloche reçoit toujours ; les canaux viennent de mes branchements et un canal non branché est grisé.") +
        '<div class="cu-carte"><h3>Par gravité</h3><div class="grille3" style="grid-template-columns:minmax(150px,1.4fr) repeat(' + CANAUX.length + ',minmax(60px,1fr))"><span></span>' + CANAUX.map((c) => '<span class="h c">' + c[1] + "</span>").join("") +
        NIVEAUX.map((n) => '<span><b>' + n[1] + '</b><br><small style="color:var(--txt-faint)">' + n[2] + "</small></span>" + CANAUX.map((c) => { const on = c[0] === "cloche" || ((p.moi && p.moi[n[0]]) || []).indexOf(c[0]) >= 0; return '<span class="c"><button class="tg' + (on ? " on" : "") + '" data-a="canal" data-n="' + n[0] + '" data-c="' + c[0] + '"' + (c[0] === "cloche" || !canal(c[0]) ? " disabled" : "") + ' title="' + (c[0] !== "cloche" && !canal(c[0]) ? "canal non branché" : "") + '"></button></span>'; }).join("")).join("") + "</div>" +
        '<p class="sub" style="margin:10px 0 0">' + esc((p.canaux && p.canaux.portes) || "") + "</p></div>" +
        '<div class="cu-carte"><h3>Heures calmes et fuseau</h3><div class="cu-g2"><div><label class="f">Fuseau horaire</label><input type="text" id="mc-fz" value="' + esc(p.prefs.fuseau) + '" placeholder="' + esc(navigateur) + '" list="mc-tz2"><datalist id="mc-tz2">' + ((typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : []).map((z) => '<option value="' + esc(z) + '">').join("")) + "</datalist>" +
        (navigateur && p.prefs.fuseau !== navigateur ? '<small class="sub">Lu du navigateur : ' + esc(navigateur) + ' <button class="cu-btn sm" data-a="fuseau-nav">Utiliser</button></small>' : "") + "</div>" +
        '<div><label class="f">Heures calmes</label><div style="display:flex;gap:8px;align-items:center"><input type="time" id="mc-d" value="' + esc(p.prefs.calme_debut) + '"> à <input type="time" id="mc-f" value="' + esc(p.prefs.calme_fin) + '"></div></div></div>' +
        '<div class="row"><div class="t"><b>Respecter les heures calmes</b><small>Seule une notification critique réveille. Les « à voir » attendent la fin.</small></div><button class="tg' + (p.prefs.calmes ? " on" : "") + '" id="mc-calmes" data-a="calmes"></button></div>' +
        '<div style="margin-top:8px"><button class="cu-btn pri" data-a="prefs">Enregistrer</button></div><p class="sub" style="margin:8px 0 0">Le fuseau est lu de votre navigateur : il n\'est jamais deviné en silence.</p></div>' +
        '<div class="cu-carte"><h3>Sourdines</h3>' + ((p.sourdines || []).length ? p.sourdines.map((s) => '<div class="row"><div class="t"><b>' + esc(s.cible_nom || s.cible) + "</b><small>" + (s.portee === "notif" ? "une notification" : "une source") + " · jusqu'au " + esc(s.fin) + '</small></div><button class="cu-btn sm" data-a="lever" data-p="' + esc(s.portee) + '" data-c="' + esc(s.cible) + '">Lever</button></div>').join("") : '<div class="cu-vide">Aucune sourdine posée.</div>') + "</div>" +
        '<div class="cu-carte"><h3>Essayer un canal</h3><div style="display:flex;gap:8px;flex-wrap:wrap">' + CANAUX.filter((c) => canal(c[0])).map((c) => '<button class="cu-btn" data-a="essai" data-c="' + c[0] + '">Essayer ' + c[1].toLowerCase() + "</button>").join("") + "</div></div>";
    }

    // ═════════ sécurité ═════════
    async function pSecu() {
      const [cles, sess, agents, journal, regles] = await Promise.all([lire("webauthn.etat"), lire("comptes.mes_sessions", { courant: jeton() }), lire("comptes.mes_agents"), lire("comptes.mon_journal", { limite: 30 }), lire("comptes.regles_mdp")]);
      S.cles = cles;
      const ks = (cles && cles.cles) || [];
      return tete("Sécurité et sessions", "Comment j'entre, et qui est entré à mon nom. Les réglages de pare-feu et d'audit de la machine restent dans l'administration.") +
        '<div class="cu-carte"><h3>Mot de passe</h3><p class="sub">' + esc((regles && regles.legende) || "") + '</p><div class="cu-g2"><div><label class="f">Actuel</label><input type="password" id="mc-mp0" autocomplete="current-password"></div><div><label class="f">Nouveau</label><input type="password" id="mc-mp1" autocomplete="new-password"></div><div><label class="f">Confirmer</label><input type="password" id="mc-mp2" autocomplete="new-password"></div></div>' +
        '<div style="margin-top:10px"><button class="cu-btn pri" data-a="mdp">Changer</button></div><div class="err" id="mc-mp-err"></div><p class="sub" style="margin:8px 0 0">Changer le mot de passe <b>ferme mes autres sessions</b> : si je le change parce qu\'il a fuité, les laisser ouvertes ne protégerait de rien.</p></div>' +
        '<div class="cu-carte"><h3>Clés de sécurité ' + (cles && cles.exigee ? chip("exigée à chaque connexion", "ok") : "") + "</h3>" + (cles && cles.disponible === false ? '<div class="cu-note">' + esc(cles.erreur || "Les clés de sécurité ne sont pas disponibles sur cette instance.") + "</div>" :
          (ks.length ? ks.map((k) => '<div class="row"><div class="t"><b>' + esc(k.libelle) + '</b><small>Ajoutée ' + esc(k.cree ? quand(k.cree) : "—") + " · dernier usage " + esc(k.dernier ? quand(k.dernier) : "jamais") + ' · repère <span class="mono">…' + esc(k.id) + '</span></small></div><button class="cu-btn sm dng" data-a="cle-retirer" data-c="' + esc(k.id) + '">Révoquer</button></div>').join("") : '<div class="cu-vide">Aucune clé enregistrée.</div>') +
          '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center"><input type="text" id="mc-cle-nom" placeholder="Nom de la clé (facultatif)" style="max-width:240px"><button class="cu-btn pri" data-a="cle-ajouter">Ajouter une clé</button></div><div class="err" id="mc-cle-err"></div>' +
          '<div class="row" style="margin-top:8px"><div class="t"><b>Exiger la clé à chaque connexion</b><small>Le mot de passe ne suffit plus. Huit codes de secours s\'affichent à l\'activation : notez-les.</small></div><button class="tg' + (cles && cles.exigee ? " on" : "") + '" data-a="cle-exiger"' + (ks.length ? "" : " disabled") + '></button></div>' +
          '<div class="row"><div class="t"><b>Codes de secours</b><small>' + (cles ? cles.secours_restants || 0 : 0) + ' restant(s) sur 8. En générer de nouveaux efface les précédents.</small></div><button class="cu-btn sm" data-a="secours"' + (ks.length ? "" : " disabled") + '>Générer</button></div><div id="mc-codes"></div>') + "</div>" +
        '<div class="cu-carte"><h3>Sessions ouvertes</h3>' + (((sess && sess.sessions) || []).map((s) => '<div class="row"><div class="t"><b>' + esc(s.agent || "Navigateur") + (s.current ? " " + chip("cette session", "acc") : "") + "</b><small>" + esc(s.ip || "") + " · ouverte " + esc(quand(s.created)) + " · dernier usage " + esc(quand(s.last_used)) + "</small></div>" + (s.current ? "" : '<button class="cu-btn sm dng" data-a="session-fermer" data-c="' + esc(s.id) + '">Fermer</button>') + "</div>").join("") || '<div class="cu-vide">Aucune session.</div>') +
          (((sess && sess.sessions) || []).length > 1 ? '<div style="margin-top:10px"><button class="cu-btn dng" data-a="sessions-autres">Fermer toutes les autres sessions</button></div>' : "") + '<p class="sub" style="margin:8px 0 0">Au plus dix sessions par compte : la plus ancienne se ferme à la onzième.</p></div>' +
        '<div class="cu-carte"><h3>Agents que j\'ai invités</h3>' + (((agents && agents.agents) || []).map((a) => '<div class="row"><div class="t"><b>' + esc(a.display_name || a.compte) + "</b><small>Dernier usage " + esc(a.dernier_vu ? quand(a.dernier_vu) : "jamais") + "</small></div>" + (a.actif ? chip("actif", "ok") + ' <button class="cu-btn sm dng" data-a="agent-revoquer" data-c="' + esc(a.compte) + '">Révoquer</button>' : chip("révoqué")) + "</div>").join("") || '<div class="cu-vide">Aucun agent invité.</div>') + "</div>" +
        '<div class="cu-carte"><h3>Journal de mon compte</h3><p class="sub">Les mêmes faits que le registre de la machine, filtrés sur moi : connexions, échecs, sessions fermées, mot de passe, et qui a consulté ma fiche.</p>' + ((journal && journal.evenements || []).length ? '<ul class="cu-tl">' + journal.evenements.map((e) => "<li><time>" + esc(quand(e.ts)) + "</time><span>" + esc(e.texte) + (e.ip ? " · " + esc(e.ip) : "") + "</span></li>").join("") + "</ul>" : '<div class="cu-vide">Rien encore.</div>') + "</div>";
    }

    // ═════════ droits et données ═════════
    async function pDonnees() {
      const [mes, cat] = await Promise.all([lire("droits.mes_droits_a_moi"), lire("droits.catalogue")]);
      const detenus = new Set((mes && mes.droits) || []), admin = !!(mes && mes.admin);
      const cle = (d) => (d.id && String(d.id).indexOf(".") > 0 ? d.id : d.module + "." + (d.droit || d.id));
      const parModule = {};
      ((cat && cat.droits) || []).forEach((d) => { if (admin || detenus.has(cle(d)) || detenus.has(d.droit || d.id)) (parModule[d.module] = parModule[d.module] || []).push(d); });
      const mods = Object.keys(parModule).sort();
      return tete("Mes droits et mes données", "Ce que je peux faire, et d'où cela me vient. C'est la vue « Qui peut… ? » des Groupes, retournée vers moi — pas une seconde matrice.") +
        '<div class="cu-carte"><h3>Mes droits ' + (admin ? chip("administrateur : tous", "acc") : chip(detenus.size + " droit(s)")) + "</h3>" +
        (mods.length ? mods.map((m) => '<div class="row"><div class="t"><b>' + esc(m) + "</b><small>" + parModule[m].map((d) => esc(d.libelle || d.droit || d.id) + (d.sensible ? " (sensible)" : "")).join(" · ") + "</small></div></div>").join("") : '<div class="cu-vide">Aucun droit particulier : les fonctions ouvertes à tous restent à vous.</div>') + "</div>" +
        '<div class="cu-carte"><h3>Mes données</h3><p class="sub">Ce que Cassandra garde de moi, et comment l\'emporter. L\'export demande de confirmer le mot de passe.</p>' +
        '<div class="row"><div class="t"><b>Exporter ma mémoire</b><small>Tous mes souvenirs, en JSON, avec l\'empreinte de l\'ensemble.</small></div><button class="cu-btn" data-a="export-memoire">Télécharger</button></div>' +
        '<div class="row"><div class="t"><b>Exporter ma fiche</b><small>Ma fiche d\'état civil et de coordonnées, en JSON.</small></div><button class="cu-btn" data-a="export-fiche">Télécharger</button></div></div>';
    }

    // ── dessin et gestes ──
    async function dessiner() {
      racine.insertAdjacentHTML("beforeend", '<div class="cu-vide" id="mc-att">…</div>');
      await etatDolibarr();
      const h = await ({ accueil: pAccueil, profil: pProfil, liens: pLiens, alertes: pAlertes, secu: pSecu, donnees: pDonnees }[S.page])();
      racine.innerHTML = h;
      if (S.page === "liens") { const U = CASS.modulesUi; $$("[data-mod]").forEach((c) => U.lierChamps(c, () => dessiner())); }
      if (S.page === "profil") lier();
    }
    function telecharger(nom, objet) {
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(objet, null, 2)], { type: "application/json" })); a.download = nom; document.body.appendChild(a); a.click(); a.remove();
    }
    function reduire(fichier) {
      return new Promise((ok, ko) => {
        const img = new Image(), url = URL.createObjectURL(fichier);
        img.onload = () => {
          const t = Math.min(img.width, img.height), c = document.createElement("canvas"); c.width = c.height = 256;
          c.getContext("2d").drawImage(img, (img.width - t) / 2, (img.height - t) / 2, t, t, 0, 0, 256, 256); URL.revokeObjectURL(url);
          c.toBlob((b) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.readAsDataURL(b); }, "image/jpeg", 0.88);
        };
        img.onerror = () => ko(new Error("image illisible")); img.src = url;
      });
    }
    function valeurs() {
      const o = {};
      $$("[data-champ]").forEach((e) => { let v = e.value; if (e.dataset.champ === "socialnetworks") v = reseauxEnJson(v); if (e.dataset.champ === "color") v = String(v).replace("#", ""); o[e.dataset.champ] = v; });
      return o;
    }
    function changes() {
      const v = valeurs(), f = S.fiche || {}, c = {};
      Object.keys(v).forEach((k) => { const avant = k === "color" ? f[k] || "" : f[k] || ""; if (String(v[k]) !== String(avant) && !(k === "color" && !f.color && v[k] === "0a726b")) c[k] = v[k]; });
      return c;
    }
    const maj = () => { const n = Object.keys(changes()).length; const b = $("#mc-barre"); if (b) { b.classList.toggle("on", n > 0); $("#mc-n").textContent = n + " modification(s) non enregistrée(s)"; } };
    racine.addEventListener("input", (e) => { if (e.target.closest("[data-champ]")) maj(); });
    racine.addEventListener("change", (e) => { if (e.target.closest("[data-champ]")) maj(); });
    function lier() {
      const f = $("#mc-fichier");
      if (f) f.addEventListener("change", async () => {
        if (!f.files[0]) return;
        try { const image = await reduire(f.files[0]); if (await geste("comptes.portrait_poser", { image: image }, "Portrait enregistré")) dessiner(); } catch (e) { dire(e.message, "err"); }
      });
    }
    async function ajouterCle() {
      const err = $("#mc-cle-err"); err.textContent = "";
      if (!window.PublicKeyCredential) { err.textContent = "Ce navigateur ne sait pas enregistrer de clé."; return; }
      try {
        const d = await agir("webauthn.defi_creer", {});
        const c = await navigator.credentials.create({ publicKey: { challenge: b64u(d.defi), rp: { name: "Cassandra", id: d.rp_id }, user: { id: b64u(versB64u(new TextEncoder().encode(d.compte))), name: d.compte, displayName: d.compte },
          pubKeyCredParams: [{ type: "public-key", alg: -7 }, { type: "public-key", alg: -257 }], authenticatorSelection: { userVerification: "required", residentKey: "required" }, timeout: 120000, attestation: "none",
          excludeCredentials: (d.exclure || []).map((id) => ({ type: "public-key", id: b64u(id) })) } });
        const r = await agir("webauthn.enregistrer", { defi: d.defi, client_data: versB64u(c.response.clientDataJSON), attestation: versB64u(c.response.attestationObject), libelle: ($("#mc-cle-nom") || {}).value || "" });
        dire("Clé enregistrée", "ok");
        await dessiner();
        const sec = r && (r.secours || r.codes); if (sec && $("#mc-codes")) $("#mc-codes").innerHTML = '<p class="sub">Codes de secours : notez-les, ils ne seront plus montrés.</p><div class="codes">' + sec.map((x) => "<span>" + esc(x) + "</span>").join("") + "</div>";
      } catch (e) { err.textContent = "Clé non enregistrée" + (e && e.message ? " (" + e.message + ")" : ""); }
    }
    async function agirSur(el) {
      const a = el.dataset.a, c = el.dataset.c;
      if (a === "aller") return ALLER(el.dataset.p)();
      if (a === "annuler") return dessiner();
      if (a === "enregistrer") {
        const ch = changes(); $("#mc-err").textContent = "";
        try { await agir("comptes.modifier_moi", ch); dire("Fiche enregistrée", "ok"); dessiner(); } catch (e) { $("#mc-err").textContent = e.message; }
        return;
      }
      if (a === "portrait-retirer") { if (await geste("comptes.portrait_retirer", {}, "Image retirée")) dessiner(); return; }
      if (a === "chercher") {
        const r = await lire("dolibarr.fiche_chercher"); const z = $("#mc-cand"); if (!z) return;
        z.innerHTML = r && r.candidats.length ? r.candidats.map((x) => '<div class="row"><div class="t"><b>' + esc(x.firstname + " " + x.lastname) + "</b><small>login " + esc(x.login) + " · " + esc(x.email) + " · n° " + x.id + '</small></div><button class="cu-btn pri sm" data-a="lier" data-c="' + x.id + '">C\'est moi</button></div>').join("") : '<div class="cu-note">' + esc(S.erreur && !r ? S.erreur : "Aucun utilisateur de Dolibarr ne porte mon adresse.") + "</div>";
        return;
      }
      if (a === "lier") { if (await geste("dolibarr.fiche_lier", { id_doli: Number(c) }, "Fiche liée")) dessiner(); return; }
      if (a === "delier") { if (await CASS.kit.confirmer("Délier ma fiche de Dolibarr ?", "<p class=\"note\">Rien n'est effacé, ni d'un côté ni de l'autre.</p>", "Délier", true) && await geste("dolibarr.fiche_delier", {}, "Fiche déliée")) dessiner(); return; }
      if (a === "envoyer") { const x = (S.cmp.champs || []).find((y) => y.champ === c); if (x && await geste("dolibarr.fiche_ecrire", { champs: { [c]: x.cassandra } }, "Envoyé vers Dolibarr")) dessiner(); return; }
      if (a === "reprendre") { const x = (S.cmp.champs || []).find((y) => y.champ === c); if (x && await geste("comptes.modifier_moi", { [c]: x.dolibarr }, "Repris depuis Dolibarr")) dessiner(); return; }
      if (a === "canal") {
        const n = el.dataset.n, deja = ((S.pol.moi && S.pol.moi[n]) || ["cloche"]).slice(), i = deja.indexOf(c); if (i >= 0) deja.splice(i, 1); else deja.push(c);
        if (deja.indexOf("cloche") < 0) deja.unshift("cloche");
        if (await geste("notifications.politique_ecrire", { niveau: n, canaux: deja }, "Enregistré")) dessiner(); return;
      }
      if (a === "miroir") { const veut = !el.classList.contains("on"); if (await geste("canaux.miroir_ecrire", { actif: veut }, veut ? "Miroir allumé" : "Miroir éteint")) dessiner(); return; }
      if (a === "calmes") { el.classList.toggle("on"); return; }
      if (a === "fuseau-nav") { try { $("#mc-fz").value = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { /* le navigateur ne le dit pas */ } return; }
      if (a === "prefs") { if (await geste("notifications.prefs", { fuseau: $("#mc-fz").value.trim(), calmes: $("#mc-calmes").classList.contains("on"), calme_debut: $("#mc-d").value, calme_fin: $("#mc-f").value }, "Enregistré")) dessiner(); return; }
      if (a === "lever") { if (await geste("notifications.sourdine", { portee: el.dataset.p, cible: c, heures: 0 }, "Sourdine levée")) dessiner(); return; }
      if (a === "essai") { const r = await geste("notifications.essai", { canal: c }); if (r) dire(r.detail || "Essai fait", r.ok === false ? "err" : "ok"); return; }
      if (a === "mdp") {
        const e = $("#mc-mp-err"); e.textContent = ""; const n1 = $("#mc-mp1").value;
        if (n1 !== $("#mc-mp2").value) { e.textContent = "Les deux nouveaux mots de passe diffèrent."; return; }
        try { const r = await agir("comptes.changer_mon_mot_de_passe", { actuel: $("#mc-mp0").value, nouveau: n1, courant: jeton() }); dire("Mot de passe changé" + (r && r.sessions_fermees ? " · " + r.sessions_fermees + " autre(s) session(s) fermée(s)" : ""), "ok"); dessiner(); } catch (x) { e.textContent = x.message; }
        return;
      }
      if (a === "cle-ajouter") return ajouterCle();
      if (a === "cle-retirer") { if (await CASS.kit.confirmer("Révoquer cette clé ?", '<p class="note">Elle ne pourra plus servir à entrer. Si c\'est la dernière, la connexion se fera de nouveau par mot de passe seul, tout de suite. Vos données et vos autres sessions ne bougent pas.</p>', "Révoquer", true) && await geste("webauthn.supprimer", { court: c }, "Clé révoquée")) dessiner(); return; }
      if (a === "cle-exiger") {
        const veut = !el.classList.contains("on");
        if (veut && !(await CASS.kit.confirmer("Exiger la clé à chaque connexion ?", '<p class="note">Votre mot de passe ne suffira plus. Ne le faites que si vous avez vérifié que la connexion par clé fonctionne. Huit codes de secours vont s\'afficher : notez-les, ils ne seront plus montrés.</p>', "Exiger", true))) return;
        const r = await geste("webauthn.exiger", { exiger: veut }); if (r) { await dessiner(); if (r.secours && $("#mc-codes")) $("#mc-codes").innerHTML = '<div class="codes">' + r.secours.map((x) => "<span>" + esc(x) + "</span>").join("") + "</div>"; } return;
      }
      if (a === "secours") { const r = await geste("webauthn.secours_regenerer", {}); if (r && r.secours && $("#mc-codes")) $("#mc-codes").innerHTML = '<p class="sub">Notez-les : ils ne seront plus montrés.</p><div class="codes">' + r.secours.map((x) => "<span>" + esc(x) + "</span>").join("") + "</div>"; return; }
      if (a === "session-fermer") { if (await geste("comptes.revoquer_session", { court: c }, "Session fermée")) dessiner(); return; }
      if (a === "sessions-autres") { if (await CASS.kit.confirmer("Fermer toutes les autres sessions ?", '<p class="note">Seule la session que vous utilisez reste ouverte.</p>', "Fermer", true) && await geste("comptes.revoquer_autres_sessions", { courant: jeton() }, "Autres sessions fermées")) dessiner(); return; }
      if (a === "agent-revoquer") { if (await geste("comptes.revoquer_agent", { nom: c }, "Agent révoqué")) dessiner(); return; }
      if (a === "export-memoire") { const r = await geste("memoire.exporter", {}); if (r) telecharger("memoire-" + new Date().toISOString().slice(0, 10) + ".json", r); return; }
      if (a === "export-fiche") { const m = await lire("comptes.moi"); if (m) telecharger("fiche-" + new Date().toISOString().slice(0, 10) + ".json", m.fiche); return; }
    }
    racine.addEventListener("click", (e) => { const b = e.target.closest("[data-a]"); if (b && b.tagName !== "SELECT") { e.preventDefault(); agirSur(b); } });
    racine.addEventListener("change", async (e) => { if (e.target.matches('select[data-a="source"]')) { if (await geste("comptes.portrait_source", { source: e.target.value }, "Source enregistrée")) dessiner(); } });
    await dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : interface/CN_comptes-ecran.js (qui l'appelle), modules/comptes (les capacités), noyau/CN_fiche.py (la fiche)
