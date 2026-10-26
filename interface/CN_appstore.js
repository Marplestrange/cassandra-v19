// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La page App Store : déposer une archive, parcourir un registre, gérer les modules installés
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #ad75dd
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La page « App Store » : on dépose une archive de module (.cmod) ou on en prend une au registre ; l'examen dit ce qu'elle est, qui l'a signée, ce qu'elle demande et ce qu'elle casserait ; l'installation exige le consentement aux permissions montrées ; les modules installés se mettent à jour, reviennent en arrière ou se désinstallent.
// MÉTHODE    : le téléversement part en octets bruts vers /api/televerser/modules.examiner (l'archive va en quarantaine, rien n'est posé) ; l'installation passe par modules.installer avec l'empreinte des permissions TELLES QUE MONTRÉES ; un module installé reste inactif jusqu'à son activation ; tout texte dynamique est échappé
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=ad75dd ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const agir = (cap, args) => CASS.agir(cap, args || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };
  const token = () => { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } };
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";
  const Mo = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " Mo" : Math.max(1, Math.round(n / 1024)) + " Ko");

  // ce que chaque catégorie de permission veut dire, en clair ; « sensible » : ce qui donne de la prise sur la maison
  const PERMS = {
    reseau: ["Se connecte à", false], ecritures: ["Écrit sur le disque dans", true], privileges: ["Lance en administrateur système", true],
    espace_utilisateur: ["Garde des données dans l’espace de chaque utilisateur", false], introspection: ["Lit les manifestes et les compteurs des autres modules", false],
    lectures: ["Appelle les lectures des autres modules", false], droits: ["Administre les droits des comptes", true], identite: ["Administre mots de passe et sessions", true],
    reglages: ["Écrit les réglages des autres modules", true], stockage: ["Garde ses données dans sa propre base", false], stockage_lecture: ["Lit la base d’autres modules", true],
    secrets: ["Chiffre et déchiffre des secrets", true], racine: ["Demande des commandes à l’administrateur système (root)", true], agir: ["Agit comme un agent", true]
  };
  const NIVEAUX = { officiel: ["Officiel", "ok"], verifie: ["Éditeur vérifié", "ac"], local: ["Clé de l’administrateur", "nu"], "": ["Non signé", "dg"] };
  const STATUTS = { nouveau: ["Nouveau", "ok"], mise_a_jour: ["Mise à jour", "ac"], identique: ["Déjà installé", "nu"], retrograde: ["Version plus ancienne", "al"] };
  const CRIT = { vital: ["Vital", "vi"], important: ["Important", "al"], optionnel: ["Optionnel", "nu"] };
  const ICO = '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><path d="M16.5 13v7M13 16.5h7"/>';

  const CSS = ".as{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.as *{box-sizing:border-box}.as h1,.as h2,.as h3,.as p{margin:0}.as .note{font-size:12.5px;color:var(--txt-soft)}.as .mono{font-family:" + MONO + "}" +
    ".as .bandeau{font-size:12.5px;background:var(--surface);border:1px solid var(--accent);border-radius:12px;padding:9px 13px;color:var(--txt-soft)}.as .bandeau.al{border-color:var(--warn)}.as .bandeau.dg{border-color:var(--danger);color:var(--danger)}" +
    ".as .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 14px;font:600 13px 'Inter',system-ui,sans-serif;cursor:pointer;white-space:nowrap}.as .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}" +
    ".as .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.as .btn.pri:hover:not([disabled]){color:var(--on-accent,#fff);filter:brightness(1.08)}.as .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.as .btn[disabled]{opacity:.45;cursor:not-allowed}.as .btn.mini{padding:4px 10px;font-size:12px}" +
    ".as .carte{background:var(--surface);backdrop-filter:blur(14px) saturate(150%);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass)}.as .onglets{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto}.as .onglets button{border:0;background:transparent;padding:10px 16px;font:600 13px 'Inter',system-ui,sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}" +
    ".as .onglets button.on{color:var(--accent);border-bottom-color:var(--accent)}.as .p{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 11px 'Inter',system-ui,sans-serif;background:var(--surface-solid,var(--surface));color:var(--txt-soft);border:1px solid var(--line);white-space:nowrap}.as .p::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}.as .p.nu::before{display:none}" +
    ".as .p.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 28%,transparent)}.as .p.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}.as .p.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent);border-color:color-mix(in srgb,var(--danger) 28%,transparent)}" +
    ".as .p.ac{color:var(--accent);background:color-mix(in srgb,var(--accent) 11%,transparent);border-color:color-mix(in srgb,var(--accent) 26%,transparent)}.as .p.vi{background:var(--txt-strong,#111);color:var(--bg,#fff);border-color:transparent}.as .p.vi::before{background:var(--danger)}" +
    ".as .depot{border:2px dashed var(--line-strong,var(--line));border-radius:18px;padding:34px 20px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:10px;background:var(--surface);cursor:pointer;transition:.15s}.as .depot.sur,.as .depot:hover{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,var(--surface))}" +
    ".as .depot svg{width:44px;height:44px;fill:none;stroke:var(--accent);stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}.as .depot h2{font:650 17px 'Inter',sans-serif}.as .depot input{display:none}" +
    ".as .exam{padding:18px 20px;display:flex;flex-direction:column;gap:14px}.as .exam .tete{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.as .exam h2{font:650 20px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.as .tags{display:flex;gap:6px;flex-wrap:wrap}" +
    ".as .lib{font:600 10.5px 'Inter',sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint);margin-bottom:6px}.as .liste{display:flex;flex-direction:column}.as .liste>div{display:flex;gap:10px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--line)}.as .liste>div:first-child{border-top:0}" +
    ".as .liste .sens{color:var(--warn);font-weight:600}.as .liste .plus{color:var(--danger);font-weight:700}.as .consent{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--surface-solid,transparent)}.as .consent input{margin-top:3px;width:16px;height:16px;flex:none}" +
    ".as .acts{display:flex;gap:8px;flex-wrap:wrap}.as .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}.as .mod{padding:14px 15px;display:flex;flex-direction:column;gap:9px}.as .mod h3{font:650 15px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.as .mod .desc{font-size:12.5px;color:var(--txt-soft);min-height:2.9em;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}" +
    ".as .vide{padding:34px 10px;text-align:center;color:var(--txt-soft)}.as .ligne{padding:12px 14px;display:flex;gap:10px 14px;align-items:center;flex-wrap:wrap}.as .ligne+.ligne{border-top:1px solid var(--line)}.as .ligne .sp{flex:1;min-width:140px}.as .hist{padding:8px 14px 12px;display:flex;flex-direction:column;gap:4px;font-size:12.5px;color:var(--txt-soft)}" +
    ".as .hist .v{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.as .ok-installe{padding:16px 18px;display:flex;flex-direction:column;gap:10px;border-color:var(--ok)}";

  CASS.pageAppStore = function (corps) {
    const anc = document.getElementById("as-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "as-css"; st.textContent = CSS; document.head.appendChild(st);
    const racine = document.createElement("div"); racine.className = "as"; corps.innerHTML = ""; corps.appendChild(racine);
    const S = { onglet: "depot", examen: null, installe: null, politique: "signes", off: null, autre: null, regChargement: false, modules: null, versions: {}, sante: {}, occupe: false, hote: "" };

    const lire = async () => {
      try { const l = await agir("reglages.lire", { module: "modules" }); const r = ((l && l.reglages) || []).find((x) => x.cle === "modules.politique_confiance"); if (r) S.politique = r.valeur || "signes"; const u = ((l && l.reglages) || []).find((x) => x.cle === "modules.registre_url"); S.hote = (u && u.valeur) || ""; } catch (e) { /* la politique par défaut est la plus stricte */ }
    };
    const occupe = async (f) => { if (S.occupe) return; S.occupe = true; dessiner(); try { return await f(); } catch (e) { dire(e.message || String(e), "err"); } finally { S.occupe = false; dessiner(); } };

    // ── les trois onglets ─────────────────────────────────────────────────────
    function dessiner() {
      const o = S.onglet;
      racine.innerHTML = '<div class="bandeau' + (S.politique === "tous" ? " al" : "") + '">' + (S.politique === "signes" ? "<b>Politique : paquets signés seulement.</b> Une archive n’est acceptée que si un éditeur dont vous avez posé la clé l’a signée. " : "<b>Politique ouverte.</b> Un paquet non signé est permis : à vos risques. ") +
        "Un module installé tourne <b>dans Cassandra</b> : ses permissions sont déclaratives, pas encore cloisonnées. N’installez que ce que vous avez de bonnes raisons de croire.</div>" +
        '<div class="onglets" role="tablist">' + [["depot", "Déposer une archive"], ["registre", "Registre"], ["installes", "Installés"]].map((t) => '<button type="button" role="tab" data-o="' + t[0] + '" class="' + (o === t[0] ? "on" : "") + '">' + t[1] + "</button>").join("") + "</div>" +
        '<div id="as-corps">' + (o === "depot" ? depot() : o === "registre" ? registre() : installes()) + "</div>";
      racine.querySelectorAll("[data-o]").forEach((b) => b.addEventListener("click", () => { S.onglet = b.dataset.o; S.examen = S.examen && o === b.dataset.o ? S.examen : null; if (S.onglet === "registre" && !S.off) chargerRegistre(); if (S.onglet === "installes" && !S.modules) chargerInstalles(); dessiner(); }));
      lier();
    }

    function depot() {
      if (S.installe) return '<div class="carte ok-installe"><h2 style="font:650 18px Inter,sans-serif">✓ ' + esc(S.installe.nom) + " v" + esc(S.installe.version) + ' installé</h2><p class="note">Le module est déposé mais <b>inactif</b> : rien de lui ne tourne tant que vous ne l’avez pas activé.</p>' +
        '<div class="acts"><button class="btn pri" data-a="activer" data-id="' + esc(S.installe.id) + '"' + (S.occupe ? " disabled" : "") + '>Activer ' + esc(S.installe.nom) + '</button><button class="btn" data-a="autre">Installer un autre module</button></div></div>';
      if (S.examen) return examen(S.examen);
      return '<div class="depot" id="as-depot" role="button" tabindex="0"><svg viewBox="0 0 24 24" aria-hidden="true">' + ICO + '</svg><h2>Déposez une archive de module ici</h2><p class="note">Un fichier <b>.cmod</b> (32 Mo au plus). Il est examiné en quarantaine : rien n’est installé avant votre accord.</p>' +
        '<button type="button" class="btn pri" data-a="choisir"' + (S.occupe ? " disabled" : "") + '>' + (S.occupe ? "Examen en cours…" : "Choisir un fichier") + '</button><input type="file" id="as-fichier" accept=".cmod,application/gzip,application/x-gzip"></div>';
    }

    function examen(e) {
      const [lib, cls] = STATUTS[e.statut] || [e.statut, ""], c = CRIT[e.importance];
      const perms = Object.entries(e.permissions || {});
      const plus = e.permissions_elargies || [];
      const manque = (e.requiert_manquants || []).concat(e.versions_insuffisantes || []);
      const bloque = !e.autorise || e.statut === "identique" || manque.length || (e.conflits || []).length || (e.casserait || []).length;
      const ok = !bloque;
      const tr = CASS.modulesUi && CASS.modulesUi.trace ? CASS.modulesUi.trace(e.icone_trace) : "";
      return '<div class="carte exam"><div class="tete">' + (tr ? '<svg viewBox="0 0 24 24" aria-hidden="true" style="width:34px;height:34px;fill:none;stroke:var(--accent);stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round">' + tr + "</svg>" : "") + '<h2>' + esc(e.nom) + '</h2><span class="mono note">' + esc(e.id) + " v" + esc(e.version) + "</span>" +
        '<div class="tags"><span class="p ' + cls + '">' + esc(lib) + (e.version_en_place ? " (en place : " + esc(e.version_en_place) + ")" : "") + "</span>" +
        '<span class="p ' + (NIVEAUX[e.niveau || ""] || NIVEAUX[""])[1] + '">' + (NIVEAUX[e.niveau || ""] || NIVEAUX[""])[0] + (e.signe && e.editeur ? " · " + esc(String(e.editeur).replace(/^(cassandra-|ed_)/, "")) : "") + "</span>" + (c ? '<span class="p ' + c[1] + '">' + c[0] + "</span>" : "") + '<span class="p nu">' + esc(Mo(e.taille)) + " · " + e.nb_fichiers + " fichiers</span></div></div>" +
        "<p>" + esc(e.description) + "</p>" + (e.sans ? '<p class="note">Sans lui : ' + esc(e.sans) + "</p>" : "") +
        ((e.raisons || []).length ? '<div class="bandeau dg"><b>Refusée.</b> ' + e.raisons.map(esc).join(" ; ") + "</div>" : "") +
        ((e.avertissements || []).map((a) => '<div class="bandeau al">' + esc(a) + "</div>").join("")) +
        '<div><div class="lib">Ce qu’il demande</div><div class="liste">' + (perms.length ? perms.map(([k, v]) => { const [t, sens] = PERMS[k] || [k, false]; return "<div><span" + (sens ? ' class="sens"' : "") + ">" + esc(t) + (v === true ? "" : " : <span class=\"mono\">" + esc((v || []).join(", ")) + "</span>") + "</span></div>"; }).join("") : '<div><span class="note">Rien : ni réseau, ni écriture, ni privilège déclaré.</span></div>') + "</div></div>" +
        (plus.length ? '<div class="bandeau dg"><b>Cette version demande de PLUS que la précédente :</b><div class="liste">' + plus.map((x) => '<div><span class="plus">+ ' + esc(x) + "</span></div>").join("") + "</div></div>" : "") +
        (manque.length || (e.conflits || []).length || (e.casserait || []).length ? '<div class="bandeau dg"><b>Ne s’installerait pas telle quelle :</b> ' + [manque.length ? "il lui manque " + manque.map(esc).join(", ") : "", (e.conflits || []).length ? "en conflit avec " + e.conflits.map(esc).join(", ") + " (actif)" : "", (e.casserait || []).length ? "casserait : " + e.casserait.map(esc).join(" ; ") : ""].filter(Boolean).join(" · ") + "</div>" :
          '<div class="note">Dépendances : ' + ((e.requiert || []).length ? "toutes présentes (" + e.requiert.map(esc).join(", ") + ")" : "aucune") + ".</div>") +
        (ok ? '<label class="consent"><input type="checkbox" id="as-consent"><span>Je comprends que ce module <b>s’exécutera dans Cassandra</b> avec les permissions ci-dessus' + (plus.length ? ", dont celles demandées <b>en plus</b>" : "") + ", et je choisis de l’installer. Il restera inactif jusqu’à son activation.</span></label>" : "") +
        '<div class="acts"><button class="btn pri" data-a="installer"' + (ok ? " disabled" : " disabled") + ' id="as-installer"' + (S.occupe ? " disabled" : "") + ">" + (e.statut === "mise_a_jour" ? "Mettre à jour" : "Installer") + '</button><button class="btn" data-a="abandonner"' + (S.occupe ? " disabled" : "") + ">Abandonner</button></div></div>";
    }

    const jour = (ts) => new Date(ts * 1000).toLocaleDateString("fr-FR");
    function carteRegistre(m, source) {
      const [nl, nc] = source === "officiel" ? (NIVEAUX[m.niveau || ""] || NIVEAUX[""]) : ["Registre non officiel", "al"];
      const bloque = !!m.revoque || m.etat === "installe" || S.occupe;
      return '<div class="carte mod"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><h3>' + esc(m.nom) + '</h3><span class="p ' + (m.etat === "nouveau" ? "ok" : m.etat === "mise_a_jour" ? "ac" : "nu") + '">' + (m.etat === "nouveau" ? "Nouveau" : m.etat === "mise_a_jour" ? "Mise à jour" : "Installé") + "</span></div>" +
        '<div class="tags"><span class="p ' + nc + '">' + nl + (source === "officiel" && m.niveau === "verifie" && m.editeur_id ? " · " + esc(m.editeur_id) : "") + "</span>" + (CRIT[m.importance] ? '<span class="p ' + CRIT[m.importance][1] + '">' + CRIT[m.importance][0] + "</span>" : "") + "</div>" +
        '<div class="mono note">' + esc(m.id) + " v" + esc(m.version) + (m.version_en_place ? " (en place : " + esc(m.version_en_place) + ")" : "") + '</div><div class="desc">' + esc(m.description) + "</div>" +
        (m.revoque ? '<div class="bandeau dg"><b>Révoqué.</b> ' + esc(m.revoque) + "</div>" : "") +
        '<div class="acts" style="margin-top:auto"><span style="flex:1"></span><button class="btn mini pri" data-a="telecharger" data-source="' + source + '" data-id="' + esc(m.id) + '"' + (bloque ? " disabled" : "") + ">" + (m.etat === "mise_a_jour" ? "Examiner la mise à jour" : "Examiner") + "</button></div></div>";
    }
    function registre() {
      if (S.regChargement || !S.off) return '<div class="vide">Lecture du registre officiel…</div>';
      const o = S.off, a = S.autre;
      let h = '<div class="carte" style="padding:14px 18px;display:flex;flex-direction:column;gap:4px"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><h2 style="font:650 17px Inter,sans-serif">Registre officiel de Cassandra</h2>' +
        (o.erreur ? "" : '<span class="p ok">index signé</span>') + '</div><div class="note">' +
        (o.erreur ? "" : "Signé par la clé racine de Cassandra (embarquée dans l’application). Émis le " + jour(o.emis) + ", valable jusqu’au " + jour(o.expire) + ". ") + 'Il est intégré à l’application : il ne se retire pas et ne se modifie pas.</div></div>';
      if ((o.installes_revoques || []).length) h += '<div class="bandeau dg"><b>Des modules installés ont été révoqués par le registre :</b><div class="liste">' + o.installes_revoques.map((x) => "<div><span><b>" + esc(x.nom) + "</b> v" + esc(x.version) + " : " + esc(x.raison) + "</span></div>").join("") + '</div><div class="acts" style="margin-top:8px"><button class="btn mini dng" data-o2="installes">Voir les modules installés</button></div></div>';
      if (o.erreur) h += '<div class="bandeau dg">Le registre officiel ne répond pas, ou son index n’est pas valide : ' + esc(o.erreur) + '. Rien n’est installé tant qu’il n’est pas lisible et signé.</div><div class="acts"><button class="btn" data-a="relire-reg">Réessayer</button></div>';
      else if (!(o.modules || []).length) h += '<div class="vide">Le registre officiel ne propose aucun module pour l’instant.</div>';
      else h += '<div class="grille">' + o.modules.map((m) => carteRegistre(m, "officiel")).join("") + "</div>";
      h += '<div class="carte" style="padding:14px 18px;display:flex;flex-direction:column;gap:8px"><h2 style="font:650 15px Inter,sans-serif">Autre registre (non officiel)</h2>';
      if (a && a.url) {
        h += '<div class="note mono">' + esc(a.url) + "</div>" + (a.erreur ? '<div class="bandeau dg">' + esc(a.erreur) + "</div>" : '<div class="bandeau al">Son index n’est pas signé par la racine de Cassandra : chaque archive y est examinée comme une archive déposée, sans présomption de confiance.</div><div class="grille">' + (a.modules || []).map((m) => carteRegistre(m, "autre")).join("") + "</div>");
      } else h += '<div class="note">Aucun. Vous pouvez en ajouter un (l’index d’un magasin tiers) dans les réglages du module Modules ; il sera toujours affiché comme non officiel.</div><div class="acts"><button class="btn mini" data-a="reglages">Ouvrir les réglages</button></div>';
      return h + "</div>";
    }

    function installes() {
      if (!S.modules) return '<div class="vide">Lecture des modules installés…</div>';
      const l = S.modules.filter((m) => m.extension);
      if (!l.length) return '<div class="carte vide"><h2 style="font:650 17px Inter,sans-serif">Aucun module installé par archive</h2><p class="note">Les modules livrés avec Cassandra se gèrent dans « Modules et Applications ». Ceux que vous installez ici apparaissent dans cette liste.</p></div>';
      return '<div class="carte">' + l.map((m) => {
        const sa = S.sante[m.id], v = S.versions[m.id];
        return '<div><div class="ligne"><div class="sp"><b>' + esc(m.nom) + '</b> <span class="mono note">' + esc(m.id) + " v" + esc(m.version) + '</span><div class="note">' + esc(m.description || "") + '</div></div><div class="tags">' +
          '<span class="p ' + (m.etat === "actif" ? "ok" : "nu") + '">' + (m.etat === "actif" ? "Actif" : m.etat === "a_installer" ? "À installer" : "Inactif") + "</span>" +
          (sa ? '<span class="p ' + (sa.verdict === "sain" ? "ok" : sa.verdict === "en_echec" ? "dg" : "al") + '">' + (sa.verdict === "sain" ? "sain" : sa.verdict === "en_echec" ? "en échec" : "à surveiller") + "</span>" : "") + '</div><div class="acts">' +
          '<button class="btn mini" data-a="versions" data-id="' + esc(m.id) + '">Versions</button>' +
          '<button class="btn mini dng" data-a="desinstaller" data-id="' + esc(m.id) + '"' + (S.occupe ? " disabled" : "") + ">" + (m.etat === "actif" ? "Désactiver et désinstaller" : "Désinstaller") + "</button></div></div>" +
          (v ? '<div class="hist">' + (v.sauvegardes.length ? v.sauvegardes.map((x) => '<div class="v"><span class="mono">v' + esc(x.version) + "</span><span>" + esc(new Date(x.ts * 1000).toLocaleString("fr-FR")) + '</span><span class="p nu">' + esc(x.raison) + '</span><button class="btn mini" data-a="remettre" data-id="' + esc(m.id) + '" data-cle="' + esc(x.cle) + '"' + (S.occupe || x.raison === "purge" ? " disabled" : "") + ">Remettre</button></div>").join("") : "<span>Aucune version sauvegardée.</span>") +
            (v.journal.length ? '<div class="note" style="margin-top:6px">' + v.journal.slice(-5).reverse().map((x) => esc(new Date(x.ts * 1000).toLocaleDateString("fr-FR")) + " · " + esc({ installe: "installé", retour: "retour arrière", desinstalle: "désinstallé", purge: "données purgées" }[x.acte] || x.acte) + (x.version ? " v" + esc(x.version) : "") + (x.par ? " par " + esc(x.par) : "")).join("<br>") + "</div>" : "") + "</div>" : "") + "</div>";
      }).join("") + "</div>";
    }

    // ── les données ───────────────────────────────────────────────────────────
    async function chargerRegistre() {
      S.regChargement = true; S.off = null; S.autre = null; dessiner();
      try { const r = await agir("modules.registre"); S.off = r.officiel || { erreur: "réponse vide", modules: [] }; S.autre = r.autre || null; if (r.politique) S.politique = r.politique; }
      catch (e) { S.off = { erreur: e.message || String(e), modules: [], installes_revoques: [] }; }
      S.regChargement = false; dessiner();
    }
    async function chargerInstalles() {
      try {
        const l = await agir("modules.lister"); S.modules = (l && l.modules) || [];
        for (const m of S.modules.filter((x) => x.extension && x.etat === "actif")) { try { S.sante[m.id] = await agir("modules.sante", { module: m.id }); } catch (e) { /* pas de santé : pas de pastille */ } }
      } catch (e) { S.modules = []; dire(e.message || String(e), "err"); }
      dessiner();
    }
    async function televerser(fichier) {
      if (!/\.cmod$/i.test(fichier.name)) { dire("Un fichier .cmod est attendu.", "err"); return; }
      if (fichier.size > 32 * 1024 * 1024) { dire("Archive trop grande (32 Mo au plus).", "err"); return; }
      await occupe(async () => {
        const r = await fetch("/api/televerser/modules.examiner?nom=" + encodeURIComponent(fichier.name), { method: "POST", headers: { "X-Session-Token": token(), Authorization: "Bearer " + token(), "X-Cassandra": "1", "Content-Type": "application/octet-stream" }, body: await fichier.arrayBuffer() });
        let d = {}; try { d = await r.json(); } catch (e) { /* corps vide */ }
        if (!r.ok || d.statut !== "faite") throw new Error(d.erreur || d.raison || d.statut || "HTTP " + r.status);
        S.examen = d.resultat;
      });
    }

    function lier() {
      racine.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); geste(b); }));
      racine.querySelectorAll("[data-o2]").forEach((b) => b.addEventListener("click", () => { S.onglet = b.dataset.o2; if (S.onglet === "installes" && !S.modules) chargerInstalles(); dessiner(); }));
      const dep = racine.querySelector("#as-depot"), fic = racine.querySelector("#as-fichier");
      if (dep && fic) {
        dep.addEventListener("click", (e) => { if (e.target === dep || e.target.tagName === "H2" || e.target.tagName === "P" || e.target.tagName === "svg") fic.click(); });
        fic.addEventListener("change", () => { if (fic.files[0]) televerser(fic.files[0]); });
        ["dragenter", "dragover"].forEach((n) => dep.addEventListener(n, (e) => { e.preventDefault(); dep.classList.add("sur"); }));
        ["dragleave", "drop"].forEach((n) => dep.addEventListener(n, (e) => { e.preventDefault(); dep.classList.remove("sur"); }));
        dep.addEventListener("drop", (e) => { const f = e.dataTransfer && e.dataTransfer.files[0]; if (f) televerser(f); });
      }
      const cc = racine.querySelector("#as-consent"), bi = racine.querySelector("#as-installer");
      if (cc && bi) cc.addEventListener("change", () => { bi.disabled = !cc.checked || S.occupe; });
    }

    async function geste(b) {
      const a = b.dataset.a, id = b.dataset.id;
      if (a === "choisir") { const f = racine.querySelector("#as-fichier"); if (f) f.click(); return; }
      if (a === "reglages") { if (CASS.ouvrirConsole) CASS.ouvrirConsole("modules", "Modules", "reglages"); return; }
      if (a === "relire-reg") { chargerRegistre(); return; }
      if (a === "autre") { S.installe = null; S.examen = null; dessiner(); return; }
      if (a === "abandonner") { const j = S.examen && S.examen.jeton; S.examen = null; dessiner(); if (j) { try { await agir("modules.abandonner", { jeton: j }); } catch (e) { /* déjà partie */ } } return; }
      if (a === "installer") {
        const e = S.examen; if (!e) return;
        await occupe(async () => {
          await agir("modules.installer", { jeton: e.jeton, consentement: e.empreinte_permissions });
          S.installe = e; S.examen = null; S.modules = null; dire(e.nom + " installé (inactif).", "ok");
        });
        return;
      }
      if (a === "activer") { await occupe(async () => { await agir("modules.activer", { module: id, avec_dependances: true }); dire("Module activé : " + id, "ok"); S.installe = null; S.modules = null; S.onglet = "installes"; await chargerInstalles(); }); return; }
      if (a === "telecharger") { await occupe(async () => { S.examen = await agir("modules.telecharger", { module: id, source: b.dataset.source || "officiel" }); S.onglet = "depot"; }); return; }
      if (a === "versions") { S.versions[id] = S.versions[id] ? null : await agir("modules.versions", { module: id }).catch((e) => { dire(e.message, "err"); return null; }); dessiner(); return; }
      if (a === "remettre") { await occupe(async () => { const r = await agir("modules.retour_arriere", { module: id, cle: b.dataset.cle }); dire("Version " + r.version + " remise.", "ok"); S.versions[id] = null; S.modules = null; await chargerInstalles(); }); return; }
      if (a === "desinstaller") {
        if (b.dataset.arme !== "1") { b.dataset.arme = "1"; b.textContent = "Confirmer ?"; b.classList.add("pri"); setTimeout(() => { if (b.isConnected) { b.dataset.arme = ""; dessiner(); } }, 4000); return; }
        await occupe(async () => {
          const m = (S.modules || []).find((x) => x.id === id);
          if (m && m.etat === "actif") await agir("modules.desactiver", { module: id, cascade: false });
          await agir("modules.desinstaller", { module: id, purger_donnees: false });
          dire("Module désinstallé : son dossier est en sauvegarde, ses données restent.", "ok"); S.versions[id] = null; S.modules = null; await chargerInstalles();
        });
      }
    }

    lire().then(dessiner);
    dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de la page et ses gestes.
// EC : néant.
// LIEN : modules/modules (examiner, installer, registre, telecharger, versions, retour_arriere, desinstaller, sante), noyau/CN_cycle.py (le cycle de vie), noyau/CN_passerelle.py (/api/televerser), tests-ui/appstore.spec.js.
