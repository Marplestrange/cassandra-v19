// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le squelette : ce que les modules déclarent se branche sur l'interface V18, sans que celle
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #3f2a85
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le squelette : ce que les modules déclarent se branche sur l'interface V18, sans que celle-ci le sache.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=3f2a85 ▼▼▼
/* Le squelette : ce que les modules déclarent se branche sur l'interface V18, sans que celle-ci le sache.

   1. Les THÈMES : un module livre un thème complet ([[habillages]] : des variables CSS). Il apparaît dans le sélecteur d'apparence,
      posé par-dessus sa base (clair, crème ou sombre) pour garder les règles propres à cette base.
   2. Le RAIL : un écran V18 dont le module n'est pas actif disparaît ; un écran de module qui n'a pas d'équivalent V18 s'ajoute dans « Modules ».
   3. La SCÈNE générique : l'écran d'un module sans écran V18 se lit par affichage.lire_ecran (zones, tuiles) et se dessine avec les jetons de la V18.
   4. Les ONGLETS d'objet : CASS.ongletsDe("notes:note") donne les onglets que les modules ajoutent à la fiche d'un objet (à la façon de Dolibarr).

   Chargé APRÈS app.js : il en modifie les tableaux (TH_ETATS, ALL_TABS) et enveloppe deux fonctions (appliquerTheme, switchTab). */
(function () {
  "use strict";
  const CASS = window.CASS;
  const token = () => { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } };
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Une capacité du noyau, appelée telle quelle. Rend le résultat ou lève l'erreur dite par le noyau.
  // La société choisie (le sélecteur à côté de l'avatar) : tout l'écran travaille dans celle-là. Vide : celle du compte. Le serveur vérifie qu'elle est bien l'une des siennes.
  CASS.societe = (function () { try { return localStorage.getItem("cn.societe") || ""; } catch (e) { return ""; } })();
  CASS.choisirSociete = function (id) { try { if (id) localStorage.setItem("cn.societe", id); else localStorage.removeItem("cn.societe"); } catch (e) { /* sans mémoire locale, le choix ne survit pas au rechargement */ } CASS.societe = id || ""; location.reload(); };
  // Un geste sensible demande le mot de passe de la session (réponse 401 « confirmation ») : une boîte le réclame, la confirmation part au noyau, le geste se redemande.
  CASS.confirmerMdp = function () {
    return new Promise((fin) => {
      const v = document.createElement("div"); v.style.cssText = "position:fixed;inset:0;background:rgba(10,20,30,.45);z-index:10000";
      const m = document.createElement("div"); m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", "Confirmer votre mot de passe"); m.className = "kit-m"; m.style.zIndex = "10001";
      m.innerHTML = "<h2>Confirmez votre mot de passe</h2><p class=\"note\">Ce geste est sensible : redonnez votre mot de passe pour continuer. Il ne sera pas redemandé pendant quelques minutes.</p>" +
        "<input type=\"password\" autocomplete=\"current-password\" aria-label=\"Mot de passe\" style=\"padding:9px 11px;border-radius:10px;border:1px solid var(--line-strong,var(--line));font:inherit\"><p class=\"note\" data-e style=\"color:var(--danger);min-height:1em;margin:0\"></p>" +
        "<div class=\"acts\"><button class=\"btn\" data-c=\"non\">Annuler</button><button class=\"btn pri\" data-c=\"oui\">Confirmer</button></div>";
      const clore = (r) => { v.remove(); m.remove(); fin(r); };
      const champ = m.querySelector("input"), err = m.querySelector("[data-e]");
      const valider = async () => {
        const r = await fetch("/api/confirmer", { method: "POST", headers: { "X-Session-Token": token(), "X-Cassandra": "1" }, body: JSON.stringify({ mot_de_passe: champ.value }) });
        if (r.ok) return clore(true);
        let d = {}; try { d = await r.json(); } catch (e) {}
        err.textContent = d.erreur || "Mot de passe incorrect"; champ.select();
      };
      v.addEventListener("click", () => clore(false));
      m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b) { if (b.dataset.c === "oui") valider(); else clore(false); } });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(false); if (e.key === "Enter") valider(); });
      document.body.appendChild(v); document.body.appendChild(m); champ.focus();
    });
  };
  CASS.agir = async function (cap, args, _redemande) {
    const h = { "X-Session-Token": token() }; if (CASS.societe) h["X-Societe"] = CASS.societe;
    const r = await fetch("/api/agir/" + cap, { method: "POST", headers: h, body: JSON.stringify({ args: args || {} }) });
    let d = {};
    try { d = await r.json(); } catch (e) {}
    if (r.status === 401 && d.confirmation && !_redemande && await CASS.confirmerMdp()) return CASS.agir(cap, args, true);
    if (!r.ok || (d.statut !== "faite" && d.statut !== "racontee" && d.statut !== "simulee")) {
      const msg = d.erreur || d.raison || d.statut || ("HTTP " + r.status);
      if (CASS.societe && /n'a pas accès à la société/.test(String(msg))) { CASS.choisirSociete(""); }      // un accès retiré entre-temps : retour à sa propre société
      throw new Error(msg);
    }
    return d.resultat;
  };
  CASS.moi = null;

  // ── 1. les thèmes ──────────────────────────────────────────────────────────
  CASS.habillages = {};
  const appliquerOrigine = window.appliquerTheme;
  window.appliquerTheme = function (t) {
    const h = CASS.habillages[t];
    const racine = document.documentElement;
    if (!h) { racine.removeAttribute("data-habillage"); return appliquerOrigine(t); }
    appliquerOrigine(h.base === "sombre" ? "dark" : h.base === "creme" ? "creme" : "light");
    racine.setAttribute("data-habillage", t);
    try { localStorage.setItem("cass_theme", t); } catch (e) {}
    const e = TH_ETATS.find((x) => x[0] === t);
    const b = document.getElementById("theme-btn");
    if (b && e) { b.innerHTML = e[2]; b.title = "Apparence : " + e[1] + " — cliquer pour changer"; }
    document.querySelectorAll("#um-seg [data-th]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.th === t)));
  };
  async function themes() {
    const r = await CASS.agir("affichage.lire_habillages", {});
    let css = "";
    for (const h of r.habillages || []) {
      const id = h.id;
      CASS.habillages[id] = h;
      const decl = Object.entries(h.variables || {}).map(([k, v]) => k + ":" + v + ";").join("");
      const base = h.base === "sombre" ? "dark" : h.base === "creme" ? "creme" : "light";
      css += ':root[data-theme="' + base + '"][data-habillage="' + id + '"]{' + decl + "color-scheme:" + (h.base === "sombre" ? "dark" : "light") + ";}\n";
      if (!TH_ETATS.some((x) => x[0] === id)) TH_ETATS.push([id, h.libelle, h.base === "sombre" ? TH_LUNE : TH_SOLEIL]);
    }
    let st = document.getElementById("habillages-modules");
    if (!st) { st = document.createElement("style"); st.id = "habillages-modules"; document.head.appendChild(st); }
    st.textContent = css;
    if (typeof umSegments === "function") umSegments();
    if (CASS.themeDemande && CASS.habillages[CASS.themeDemande]) window.appliquerTheme(CASS.themeDemande);
  }

  // ── 2. le rail ─────────────────────────────────────────────────────────────
  // Quel module fait vivre quel écran V18. Un écran dont le module n'est pas actif n'est pas proposé ; les écrans sans module connu restent.
  CASS.dependances = { evolution: ["evolution"], memory: ["memoire"], sensorium: ["sensorium"], overview: ["vue"], history: ["mesures"], securite: ["securite"], mysites: ["sites"], fastpanel: ["fastpanel"] };
  // Les modules qu'un écran V18 couvre déjà : leur entrée de menu ne s'ajoute pas une seconde fois.
  CASS.couvre = { evolution: "evolution", memoire: "memory", sensorium: "sensorium", sites: "mysites", fastpanel: "fastpanel", courrier: "bureau", notes: "bureau", taches: "bureau", agenda: "bureau", contacts: "bureau", projets: "bureau", comptes: "settings", modeles: "settings", agents: "salon", salon: "salon", journal: "journal", notifications: "bureau", planifie: "crons", flotte: "fleet", vue: "overview", mesures: "history", securite: "securite" };
  function actifs(modules) { return new Set((modules || []).filter((m) => m.etat === "actif" || m.actif).map((m) => m.id)); }

  function rail(modules, arbre) {
    const ok = actifs(modules);
    document.querySelectorAll(".sb-item[data-tab]").forEach((it) => {
      const dep = CASS.dependances[it.getAttribute("data-tab")];
      if (dep && !dep.every((m) => ok.has(m))) { it.style.display = "none"; it.setAttribute("data-absent", "1"); } else if (it.getAttribute("data-absent")) { it.style.display = ""; it.removeAttribute("data-absent"); }
    });
    // le groupe des modules : les entrées de menu dont le module n'a pas d'écran V18, GROUPÉES PAR FAMILLE
    const groupes = [];
    for (const famille of arbre || []) {
      const feuilles = [];
      (function marcher(ns) { for (const n of ns || []) { if (n.ecran) feuilles.push(n); marcher(n.enfants); } })(famille.enfants || []);
      const propres = feuilles.filter((f) => !CASS.couvre[f.module]);
      if (propres.length) groupes.push({ libelle: famille.libelle || famille.famille, entrees: propres });
    }
    let g = document.getElementById("sb-modules");
    if (g) g.remove();
    if (!groupes.length) return;
    g = document.createElement("div");
    g.className = "sb-group open"; g.id = "sb-modules"; g.setAttribute("data-grp", "modules");
    const sous = groupes.map((gr) =>
      '<div class="sb-fam" style="padding:5px 14px 2px;font-size:10px;text-transform:uppercase;letter-spacing:.04em;opacity:.55">' + esc(gr.libelle) + "</div>" +
      gr.entrees.map((f) => '<div class="sb-item" data-tab="' + esc(nomOnglet(f.ecran)) + '" onclick="switchTab(\'' + esc(nomOnglet(f.ecran)) + '\')"><span class="sb-dot"></span>' + esc(f.libelle) + "</div>").join("")
    ).join("");
    g.innerHTML = '<div class="sb-head" onclick="sbToggle(this)">Modules <span class="sb-caret">▸</span></div><div class="sb-sub">' + sous + "</div>";
    document.getElementById("sidebar").appendChild(g);
    for (const gr of groupes) for (const f of gr.entrees) preparerScene(f.ecran, f.libelle);
  }
  const nomOnglet = (ecran) => "mod-" + String(ecran).replace(/[^a-z0-9]+/gi, "-");

  // ── 3. la scène générique ──────────────────────────────────────────────────
  // Une phrase sous le titre pour les pages qui n'ont pas de tête à elles (les autres l'ont déjà : h1 + phrase).
  const SOUS = {
    "societes:s_identite": "Le nom, la forme et les références officielles de la société.", "societes:s_etabs": "Les lieux où la société travaille.",
    "societes:s_horaires": "Quand la société est ouverte, et son calendrier.", "societes:s_presence": "Où la société existe en ligne.",
    "societes:s_equipe": "Les personnes qui répondent de la société.", "societes:s_fonctions": "Les fonctions de la société et les droits qu’elles donnent.",
    "societes:s_pieces": "Les pièces officielles de la société et leurs échéances.", "societes:s_banque": "Les comptes bancaires et les informations de facturation.",
    "societes:s_conformite": "Ce que la société doit respecter, et où elle en est.", "societes:s_habillage": "L’apparence de la société : couleurs, logo, modèles de documents.",
    "societes:s_coffre": "Les secrets de la société, séparés de ceux des autres.", "societes:s_modules": "Les modules ouverts dans cette société.",
    "societes:s_carnet": "Le carnet de notes de la société.", "societes:s_partages": "Ce que la société partage avec d’autres, et avec qui.",
    "societes:s_reglages": "Les réglages propres à la société.", "societes:s_profil": "Ton rôle et tes droits dans cette société.",
    "societes:s_sert": "Où la société est utilisée dans l’application.", "societes:s_multi": "Les sociétés de l’instance et le passage de l’une à l’autre.",
    "societes:s_histo": "Ce qui a changé dans la fiche de la société.",
    "flotte:vue_flotte": "Les machines du parc : leur présence, leur disponibilité, ce que Tailscale et SSH en disent.",
    "coffre:c_tableau": "Le coffre de secrets de Cassandra, tenu par Vaultwarden.", "coffre:c_secrets": "Le coffre de secrets de Cassandra, tenu par Vaultwarden.",
    "coffre:c_outils": "Le coffre de secrets de Cassandra, tenu par Vaultwarden.", "coffre:c_rapport": "Le coffre de secrets de Cassandra, tenu par Vaultwarden.",
    "journal:vue_journal": "Les consultations des agents et tous les journaux de la machine, au même endroit.",
    "salon:vue_salon": "Des fils où les personnes et les agents se parlent.",
    "planifie:vue_taches": "Tout ce qui tourne tout seul sur la machine, et est-ce que ça va.",
    "menus:vue_mes_applications": "Les modules et applications auxquels ton compte a accès.",
    "dolibarr:d_capacites": "Ce que le pont Dolibarr sait faire pour Cassandra.", "dolibarr:d_instance": "L’instance Dolibarr à laquelle Cassandra est reliée.",
  };
  function preparerScene(ecran, titre) {
    const nom = nomOnglet(ecran);
    if (document.getElementById("tab-" + nom)) return;
    const d = document.createElement("div");
    d.id = "tab-" + nom; d.className = "tab-content"; d.setAttribute("data-scene", ecran);
    d.innerHTML = '<div class="sh-scene"><h2 class="sh-titre">' + esc(titre) + '</h2>' + (SOUS[ecran] ? '<p class="sh-sous">' + esc(SOUS[ecran]) + "</p>" : "") + '<div class="sh-corps"><div class="empty-state">Chargement…</div></div></div>';
    const hote = document.querySelector(".app-main");
    (hote || document.body).appendChild(d);
    if (ALL_TABS.indexOf(nom) < 0) ALL_TABS.push(nom);
  }
  const nombre = (x) => (typeof x === "number" ? (Number.isInteger(x) ? String(x) : x.toFixed(1)) : esc(x));
  function valeurDe(d) {
    if (d == null) return null;
    if (typeof d !== "object") return d;
    for (const k of ["valeur", "n", "nombre", "total", "score"]) if (d[k] != null) return d[k];
    return null;
  }
  function tuile(w) {
    const d = w.donnees, erreur = d && d.erreur;
    let corps;
    const v = valeurDe(d);
    if (erreur) corps = '<div class="sh-muet">' + esc(erreur) + "</div>";
    else if (d == null) corps = '<div class="sh-muet">en attente de la première lecture</div>';
    else if (w.composant === "jauge" && typeof v === "number") corps = '<div class="sh-grand">' + nombre(v) + '<small>%</small></div><div class="sh-jauge"><i style="width:' + Math.max(0, Math.min(100, v)) + '%"></i></div>';
    else if (w.composant === "etat") corps = '<div class="sh-etat">' + esc(d.etat || v || "?") + "</div>" + (d.detail ? '<div class="sh-muet">' + esc(d.detail) + "</div>" : "");
    else if (w.composant === "liste") {
      const l = Array.isArray(d) ? d : d.lignes || d.liste || d.elements || [];
      corps = l.length ? "<ul class=\"sh-liste\">" + l.slice(0, 8).map((x) => "<li>" + esc(typeof x === "object" ? x.libelle || x.titre || x.nom || JSON.stringify(x) : x) + "</li>").join("") + "</ul>" : '<div class="sh-muet">rien à signaler</div>';
    } else if (w.composant === "serie") {
      const s = (Array.isArray(d) ? d : d.points || d.serie || []).map(Number).filter((x) => !isNaN(x));
      corps = s.length > 1 ? sparkline(s) : '<div class="sh-muet">pas assez de points</div>';
    } else if (w.composant === "texte") corps = "<p>" + esc(typeof d === "string" ? d : d.texte || v || "") + "</p>";
    else corps = v != null ? '<div class="sh-grand">' + nombre(v) + "</div>" : '<div class="sh-muet">' + esc(JSON.stringify(d).slice(0, 120)) + "</div>";
    return '<section class="sh-tuile sh-t-' + esc(w.taille) + '"><div class="sh-lib">' + esc(w.libelle) + "</div>" + corps + "</section>";
  }
  function sparkline(s) {
    const mn = Math.min.apply(null, s), mx = Math.max.apply(null, s), W = 160, H = 40, dx = W / (s.length - 1);
    const pts = s.map((y, i) => (i * dx).toFixed(1) + "," + (H - 2 - ((y - mn) / ((mx - mn) || 1)) * (H - 4)).toFixed(1)).join(" ");
    return '<svg class="sh-spark" viewBox="0 0 ' + W + " " + H + '"><polyline fill="none" stroke="var(--accent)" stroke-width="1.6" points="' + pts + '"/></svg>';
  }
  async function dessinerScene(nom) {
    const racine = document.getElementById("tab-" + nom);
    if (!racine) return;
    const corps = racine.querySelector(".sh-corps");
    try {
      const moi = CASS.moi || (CASS.moi = await (await fetch("/api/moi", { headers: { "X-Session-Token": token() } })).json());
      const ecran = racine.getAttribute("data-scene");
      const surMesure = (CASS.sceneSurMesure || {})[String(ecran).split(":")[0]];      // un module qui a SON écran (évolution…) le dessine lui-même ; les autres reçoivent la scène générique
      if (surMesure) { corps.innerHTML = ""; await surMesure(corps, { ecran: ecran, moi: moi }); return; }
      let zones = {};
      try { zones = (await CASS.agir("affichage.lire_ecran", { ecran, role: moi.admin ? "admin" : "utilisateur", compte: moi.compte })).zones || {}; } catch (e) { zones = {}; }
      const html = ["entete", "principal", "lateral"].map((z) => (zones[z] || []).map(tuile).join("")).join("");
      // les tuiles que le module déclare, puis SA CONSOLE (lectures, gestes, réglages) : un module neuf a un écran utilisable sans qu'on l'écrive
      corps.innerHTML = (html ? '<div class="sh-grille">' + html + "</div>" : "") + '<div class="sh-console"></div>';
      if (CASS.console) CASS.console(String(ecran).split(":")[0], corps.querySelector(".sh-console"));
    } catch (err) { corps.innerHTML = '<div class="empty-state">' + esc(err.message) + "</div>"; }
  }
  // Ouvrir l'écran d'un module (« module:ecran »), de n'importe où : la disposition s'en sert pour ses entrées.
  CASS.nomOnglet = nomOnglet;
  CASS.ouvrirEcran = function (ecran, titre) { preparerScene(ecran, titre || ecran); window.switchTab(nomOnglet(ecran)); };
  // Ouvrir la console d'un module, de n'importe où (Réglages › Modules, par exemple).
  CASS.ouvrirConsole = function (mid, nom, onglet) {
    CASS.ongletConsole = onglet || null;                       // l'onglet par lequel la console s'ouvre (« reglages » : l'engrenage d'une carte de module)
    const ecran = mid + ":console";
    preparerScene(ecran, nom || mid);
    window.switchTab(nomOnglet(ecran));
  };
  // Un écran de module qui REMPLACE un onglet V18 (même nom) : le contenu de l'onglet est vidé et redessiné par le module.
  async function remplacerV18(onglet, mid) {
    const racine = document.getElementById("tab-" + onglet), dessin = (CASS.sceneSurMesure || {})[mid];
    if (!racine || !dessin) return;
    racine.innerHTML = '<div class="sh-scene"><h2 class="sh-titre">' + esc({ evolution: "Évolution", sensorium: "Sensorium" }[onglet] || onglet) + '</h2><div class="sh-corps"></div></div>';
    try {
      const moi = CASS.moi || (CASS.moi = await (await fetch("/api/moi", { headers: { "X-Session-Token": token() } })).json());
      await dessin(racine.querySelector(".sh-corps"), { ecran: mid + ":cockpit", moi: moi });
    } catch (err) { racine.querySelector(".sh-corps").innerHTML = '<div class="empty-state">' + esc(err.message) + "</div>"; }
  }
  const switchTabOrigine = window.switchTab;
  window.switchTab = function (name, sansHistorique) {
    const r = switchTabOrigine.apply(this, arguments);
    if (typeof name === "string" && name.indexOf("mod-") === 0) dessinerScene(name);
    if (name === "evolution") remplacerV18("evolution", "evolution");               // l'ancienne page V18 de l'évolution cède la place à l'écran du module
    if (name === "sensorium") remplacerV18("sensorium", "sensorium");               // de même pour le Sensorium (interface/CN_sensorium-ecran.js) ; le code V18 reste dans app.js
    return r;
  };

  // ── 4. les onglets d'objet ─────────────────────────────────────────────────
  CASS.ongletsDe = async function (objet) {
    const moi = CASS.moi || (CASS.moi = await (await fetch("/api/moi", { headers: { "X-Session-Token": token() } })).json());
    return (await CASS.agir("affichage.lire_onglets", { objet: objet, role: moi.admin ? "admin" : "utilisateur", compte: moi.compte })).onglets || [];
  };

  // ── le départ ──────────────────────────────────────────────────────────────
  CASS.demarrer = async function () {
    if (!token()) return;
    try {
      const [mods, menu] = await Promise.all([
        fetch("/api/modules", { headers: { "X-Session-Token": token() } }).then((r) => r.json()),
        fetch("/api/menu", { headers: { "X-Session-Token": token() } }).then((r) => r.json()),
      ]);
      rail(mods.modules, (menu.resultat || {}).arbre);
    } catch (e) { console.warn("rail :", e); }
    try { await themes(); } catch (e) { console.warn("thèmes :", e); }
  };
  CASS.surConnexion = CASS.demarrer;
  CASS.demarrer();
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
