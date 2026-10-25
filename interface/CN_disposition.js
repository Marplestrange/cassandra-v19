// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La disposition V19 : barre du haut (groupes), colonne de gauche, menu de l'avatar conservé
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #36c70e
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La disposition V19 : barre du haut (groupes), colonne de gauche, menu de l'avatar conservé, panneau conversationnel (Itare, Cassandra, invités).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=36c70e ▼▼▼
/* La disposition V19 : barre du haut (groupes), colonne de gauche, menu de l'avatar conservé, panneau conversationnel (Itare, Cassandra, invités).
   Tout ce qui est CHOISI (groupes, ordre, interlocuteur, idées) vient du serveur : affichage.lire_disposition, lire_idees, lire_fils. Ce fichier dessine et relie à l'ancienne interface
   (onglets V18) ; il ne décide d'aucun accès : le serveur filtre, l'exécuteur refait chaque vérification. Retour à l'ancienne disposition : ?disposition=v18. */
(function () {
  "use strict";
  const CASS = window.CASS;
  if (!CASS) return;
  const MODE = (function () {
    try {
      const q = new URLSearchParams(location.search).get("disposition");
      if (q === "v18" || q === "v19") localStorage.setItem("cass_disposition", q);
      return q || localStorage.getItem("cass_disposition") || "v19";
    } catch (e) { return "v19"; }
  })();
  if (MODE === "v18") return;

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const token = () => { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } };
  const agir = (cap, args) => CASS.agir(cap, args || {});

  // ── les pictogrammes (traits, jamais d'emoji) ──────────────────────────────
  const IC = {
    home: '<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z"/>',
    ticket: '<path d="M3 9a2 2 0 0 0 0 6v3a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-3a2 2 0 0 1 0-6V6a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1zM14 5v14" stroke-dasharray="2 2.5"/>',
    panorama: '<rect x="3" y="3" width="8" height="10" rx="2"/><rect x="13" y="3" width="8" height="6" rx="2"/><rect x="13" y="11" width="8" height="10" rx="2"/><rect x="3" y="15" width="8" height="6" rx="2"/>',
    health: '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    fleet: '<rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    cert: '<rect x="4" y="4" width="16" height="12" rx="2"/><circle cx="12" cy="10" r="2.5"/><path d="M9 20l3-3 3 3v-4h-6z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    scroll: '<path d="M7 4h11a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7M7 4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2M9 9h7M9 13h7"/>',
    evo: '<path d="M12 21V9M12 9c0-3 2-5 6-5 0 4-2 6-6 6M12 13c0-2-1.5-4-5-4 0 3 1.5 5 5 5"/>',
    bolt: '<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>',
    brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 3 3 3 0 0 0 1 5 3 3 0 0 0 4 4V4zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 3 3 3 0 0 1-1 5 3 3 0 0 1-4 4V4z"/>',
    desk: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>',
    puzzle: '<path d="M10 4a2 2 0 1 1 4 0v2h4a1 1 0 0 1 1 1v4h-2a2 2 0 1 0 0 4h2v4a1 1 0 0 1-1 1h-4v-2a2 2 0 1 0-4 0v2H6a1 1 0 0 1-1-1v-4h2a2 2 0 1 0 0-4H5V7a1 1 0 0 1 1-1h4z"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    db: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    repeat: '<path d="M17 2l3 3-3 3M20 5H8a4 4 0 0 0-4 4v1M7 22l-3-3 3-3M4 19h12a4 4 0 0 0 4-4v-1"/>',
    archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
    alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    bot: '<rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01M9 16.5h6"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    spark: '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>',
    star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    building: '<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
    palette: '<path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-1 2-2 0-1.5-1-1.7-1-3a2 2 0 0 1 2-2h2a4 4 0 0 0 4-4c0-4-4-7-9-7z"/><path d="M8 10h.01M12 7h.01M16 10h.01"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    down: '<path d="M6 9l6 6 6-6"/>', up: '<path d="M18 15l-6-6-6 6"/>', right: '<path d="M9 6l6 6-6 6"/>', left: '<path d="M15 6l-6 6 6 6"/>',
    lock: '<rect x="4" y="10" width="16" height="10" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>', key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', dots: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5"/>',
    tasks: '<rect x="3.5" y="4" width="17" height="16" rx="2.5"/><path d="M8.5 12l2.5 2.5 4.5-5"/>', mail: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 6.5l8.5 6 8.5-6"/>',
    contacts: '<rect x="4" y="3.5" width="15" height="17" rx="2"/><path d="M4 8H2M4 12H2M4 16H2"/><circle cx="11.5" cy="10.5" r="2.3"/><path d="M7.8 16.6c.8-1.7 2.1-2.5 3.7-2.5s2.9.8 3.7 2.5"/>',
    bell: '<path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 8H4c0-1 2-2 2-8M10 20a2 2 0 0 0 4 0"/>',
    folder: '<path d="M4 7.5a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/>',
  };
  // les icônes des vues de l'accueil : celles que portait l'ancienne pastille « Mon bureau », reportées au menu de gauche
  const VUE_IC = { calendrier: "calendar", taches: "tasks", rappels: "bell" };
  // le logo de Cassandra : le toit (celui de l'ancienne interface) ; il tient lieu de logo tant que l'organisation n'a pas le sien
  const TOIT = '<svg class="d-i toit" viewBox="0 0 24 24"><path d="M4 11.5l8-7 8 7"/><path d="M6.5 20h11"/><circle cx="12" cy="14.5" r="2.4" fill="currentColor" stroke="none"/></svg>';
  let faviconOrigine = null;
  function favicon(logo) {
    let l = document.querySelector('link[rel="icon"]');
    if (!l) { l = document.createElement("link"); l.setAttribute("rel", "icon"); document.head.appendChild(l); }
    if (faviconOrigine === null) faviconOrigine = { href: l.getAttribute("href") || "/favicon.svg", type: l.getAttribute("type") || "image/svg+xml" };
    const m = /^data:(image\/[a-z+]+);/.exec(logo || "");
    l.setAttribute("type", m ? m[1] : faviconOrigine.type);
    l.setAttribute("href", m ? logo : faviconOrigine.href);
  }
  const ico = (k, c) => '<svg class="d-i' + (c ? " " + c : "") + '" viewBox="0 0 24 24">' + (IC[k] || IC.plus) + "</svg>";

  // ── l'état ─────────────────────────────────────────────────────────────────
  const E = {
    d: null, moi: null, compte: "", g: "", e: "", vue: "", actif: null, side: "full", sideAvant: "full", sideTouche: false, ouv: new Set(),
    panel: false, manual: null, sel: { itare: "page", cassandra: "page", inv: "page" }, fils: { itare: [], cassandra: [], inv: [] }, msgs: {}, dernier: {},
    invites: new Set(["itare"]), fmenu: false, sug: false, regOuvert: false, idees: { mode: "itare", idees: [], urgent: false, actes: {} }, actes: { itare: [], cassandra: [], inv: [] },
    fil: null, lateral: null, pageNom: "", famModules: "tous", crMenu: null, crumbs: [],
    faits: new Set(), refuses: new Set(), nouveau: { itare: false, cassandra: false, inv: false }, attente: 0, rec: [], ms: false, w: "l",
    prefs: { verre: true }, brouillon: "",
  };
  try { Object.assign(E.prefs, JSON.parse(localStorage.getItem("cass_prefs19") || "{}")); } catch (e) {}
  const sauverPrefs = () => { try { localStorage.setItem("cass_prefs19", JSON.stringify(E.prefs)); } catch (e) {} };
  const ent = () => (E.d && E.d.groupes.find((g) => g.id === E.g)) || (E.d && E.d.groupes[0]) || null;
  const entree = () => { const g = ent(); return g && (g.entrees.find((x) => x.id === E.e) || g.entrees[0]); };
  const isPetit = () => E.w === "s" || E.w === "xs";
  const isXs = () => E.w === "xs";
  const tactile = () => { try { return !!(window.matchMedia && matchMedia("(pointer:coarse)").matches); } catch (e) { return false; } };

  // ── le pont vers les onglets de l'ancienne interface ───────────────────────
  // les pages du bureau de l'ancienne interface : une entrée (ou une sous-page de l'Agenda) ouvre son segment
  const SEG_ENTREE = { accueil: "today", projets: "proj", notes: "notes", courrier: "mail", repertoire: "rep", documents: "doc" };
  const SEG_VUE = { calendrier: "cal", taches: "tk", rappels: "rem" };
  // et l'inverse : quand on navigue DANS le bureau (une pastille, un lien), le menu de gauche suit
  const VERS_MENU = { today: ["accueil", ""], cal: ["agenda", "calendrier"], tk: ["agenda", "taches"], rem: ["agenda", "rappels"], proj: ["projets", ""], notes: ["notes", ""], carnet: ["notes", ""],
    canvas: ["notes", ""], liens: ["notes", ""], fusion: ["notes", ""], menage: ["notes", ""], ranger: ["notes", ""], mail: ["courrier", ""], rep: ["repertoire", ""], doc: ["documents", ""] };
  function pontVue(entreeId, vue) {
    const seg = vue ? SEG_VUE[vue] : SEG_ENTREE[entreeId];
    if (seg) setTimeout(function () { if (typeof window.buSeg === "function") window.buSeg(seg); }, 80);
    if (entreeId === "panorama") {
      if (vue === "systeme") {
        if (typeof window.ouvrirSysteme === "function") window.ouvrirSysteme();
      } else if (typeof window.vuAller === "function" && vue) {
        setTimeout(function() { window.vuAller(vue); }, 80);
      }
    }
    if (entreeId === "flotte" && typeof window.flVue === "function" && vue) {
      setTimeout(function() { window.flVue(vue); }, 80);
    }
  }

  // ── rendu dynamique du rail Flotte dans le menu de gauche ───────────────
  // `FL2` est déclaré par « const » dans l'ancienne interface : il n'est pas sur window, on le lit par son nom (typeof protège de son absence).
  const parcFlotte = () => (typeof FL2 !== "undefined" && FL2 && FL2.parc ? FL2 : null);
  function rendreFlotteRail() {
    const F = parcFlotte();
    if (!F) return '<div class="d19-fl-att">Lecture du parc…</div>';
    const M = F.parc.machines || [];
    if (!M.length) return "";
    const groupes = ["Serveurs", "Postes", "Mobiles", "Retirées", "Disparues"];
    let h = "";
    for (const g of groupes) {
      const ms = M.filter((m) => m.groupe === g);
      if (!ms.length) continue;
      h += '<div class="d19-fl-grp">' + esc(g) + "</div>";
      for (const m of ms) {
        const on = F.vue === "machine" && F.sel === m.nom;
        const st = m.etat === "erreur" ? "hors ligne" : (m.statut === "retiree" ? "retirée" : (m.niveau === "agent" ? "agent" : m.niveau === "ssh" ? "ssh" : ""));
        const dot = m.etat === "erreur" ? "danger" : (m.etat === "avert" ? "warn" : (m.etat === "ok" ? "ok" : "ghost"));
        h += '<button class="d19-si sub d19-fl-m' + (on ? " on" : "") + '" type="button" data-fm="' + esc(m.nom) + '" title="' + esc(m.libelle || "") + '"><span class="mx-dot ' + dot + '"></span><span>' + esc(m.nom) + "</span>" + (st ? '<span class="d19-fl-st' + (m.etat === "erreur" ? " off" : "") + '">' + esc(st) + "</span>" : "") + "</button>";
      }
    }
    h += '<button class="d19-si sub d19-fl-act" type="button" data-fa="ajouter">' + ico("plus") + "<span>Déclarer une machine</span></button>";
    h += '<button class="d19-si sub d19-fl-act" type="button" data-fa="relever" title="Relire le parc">' + ico("refresh") + "<span>Relever</span></button>";
    return h;
  }
  // l'état de chaque section de la Vue d'ensemble (« panne », « 7 att. »…) : l'ancienne interface l'écrit dans ses éléments d'origine, on le recopie dans le menu
  const SECTIONS_ETAT = ["verdict", "gestes", "cass", "sites", "flotte", "fil", "machine"];
  function recopierEtatPanorama() {
    SECTIONS_ETAT.forEach((id) => {
      const st = document.getElementById("vust-" + id), dot = document.getElementById("vudot-" + id);
      document.querySelectorAll('#d19-side [data-mst="' + id + '"]').forEach((x) => { x.textContent = st ? st.textContent : ""; });
      document.querySelectorAll('#d19-side [data-mdot="' + id + '"]').forEach((x) => { x.className = "mx-dot " + (dot ? dot.className.replace(/^mx-dot\s*/, "") : ""); });
    });
  }
  function suivreSegment(seg) {
    const v = VERS_MENU[seg]; if (!v || !E.d) return;
    const g = E.d.groupes.find((x) => x.id === "desk"); if (!g || !g.entrees.some((e) => e.id === v[0])) return;
    if (E.actif && E.g === "desk" && E.e === v[0] && (E.vue || "") === v[1]) return;
    aller("desk", v[0], v[1], true);
  }
  function ouvrirNoeud(n, vue) {
    if (n.onglet) { window.switchTab(n.onglet); pontVue(n.id.split(".")[0], vue || n.vue || ""); }
    else if (n.ecran === "menus:vue_modules") ouvrirModules(E.famModules || "tous");
    else if (n.ecran && CASS.ouvrirEcran) CASS.ouvrirEcran(n.ecran, n.libelle);
  }
  function chemin() { const g = ent(), e = entree(); if (!g || !e) return ""; return g.libelle + " › " + e.libelle + (E.vue ? " › " + ((e.enfants.find((f) => (f.vue || f.id) === E.vue) || {}).libelle || E.vue) : ""); }
  const cleDe = (g, e, v) => [g, e, v || ""].join("|");
  const pageCle = () => (E.actif ? cleDe(E.actif.g, E.actif.e, E.actif.vue) : "hors|" + (E.hors || ""));

  function aller(gid, eid, vue, sansOuvrir) {
    if (!E.d) return;
    const g = E.d.groupes.find((x) => x.id === gid) || E.d.groupes[0];
    if (!g) return;
    if (g.id !== E.g) E.manual = null;
    const e = g.entrees.find((x) => x.id === eid) || g.entrees[0];
    const fils = e.enfants || [];
    const f = fils.find((x) => (x.vue || x.id) === vue) || null;
    E.g = g.id; E.e = e.id; E.vue = f ? (f.vue || f.id) : (fils[0] && !vue ? (fils[0].vue || fils[0].id) : ""); E.ouv.add(e.id); E.hors = "";
    E.actif = { g: E.g, e: E.e, vue: E.vue };
    noter();
    if (!sansOuvrir) { const cible = fils.find((x) => (x.vue || x.id) === E.vue); ouvrirNoeud(cible && (cible.onglet || cible.ecran) ? cible : e, E.vue); }
    rendre();
    if (isPetit()) fermerSide();
    idees();
  }
  function noter() {
    const g = ent(), e = entree(); if (!g || !e) return;
    const k = cleDe(E.g, E.e, E.vue);
    E.rec = [{ k, g: E.g, e: E.e, v: E.vue, l: chemin() }].concat(E.rec.filter((r) => r.k !== k)).slice(0, 6);
  }
  // une page ouverte ailleurs que par la disposition (notification, lien, bouton) : on suit
  function suivre(nom) {
    if (!E.d || E.silence) return;
    const pg = PAGES_V18[nom];
    if (pg) { entrerPageV18(nom, pg); return; }                          // une page de l'ancienne interface qui a sa colonne (le coffre)
    if (nom !== E.pageNom) { E.fil = null; E.lateral = null; E.pageNom = ""; }
    let trouve = null;
    for (const g of E.d.groupes) for (const e of g.entrees) {
      if (e.onglet === nom && !trouve) trouve = { g: g.id, e: e.id, vue: E.actif && E.actif.e === e.id ? E.actif.vue : "" };
      else if (e.ecran && CASS.nomOnglet && CASS.nomOnglet(e.ecran) === nom) trouve = { g: g.id, e: e.id, vue: "" };
      else for (const f of e.enfants) if (f.ecran && CASS.nomOnglet && CASS.nomOnglet(f.ecran) === nom) trouve = { g: g.id, e: e.id, vue: f.vue || f.id };
    }
    if (trouve && !trouve.vue) { const ee = E.d.groupes.find((g) => g.id === trouve.g).entrees.find((e) => e.id === trouve.e); if (ee && ee.enfants.length && ee.onglet === nom) trouve.vue = ee.enfants[0].vue || ee.enfants[0].id; }   // sans vue dite : la première (Aujourd'hui)
    if (trouve) { E.g = trouve.g; E.e = trouve.e; E.vue = trouve.vue; E.actif = trouve; E.hors = ""; E.ouv.add(trouve.e); }
    else { E.actif = null; E.hors = nom; }
    rendre();
  }

  // ── le rendu : haut ────────────────────────────────────────────────────────
  const pastille = (g) => (g.niveau === "danger" || g.niveau === "alerte" ? '<span class="d19-dot ' + g.niveau + '"></span>' : "");
  function rendreHaut() {
    if (!E.d) return;
    const lg = $("#d19-logo"), o = E.d.organisation || {};
    const logoBarre = o.logo || o.logo_carre || "";
    lg.className = "d19-logo" + (logoBarre ? " img" : "") + (E.d.niveau === "danger" ? " s-danger" : E.d.niveau === "alerte" ? " s-alerte" : "");
    lg.title = (o.nom || "Cassandra") + " · " + (E.d.niveau === "danger" ? "un point urgent à regarder" : E.d.niveau === "alerte" ? "des points à regarder" : "tout est en ordre");
    lg.style.backgroundImage = logoBarre ? "url(" + logoBarre + ")" : "";
    lg.innerHTML = logoBarre ? "" : TOIT;
    favicon(o.logo_carre || o.logo);
    $("#d19-groupes").innerHTML = E.d.groupes.map((g, i) => '<button class="d19-gr' + (g.id === E.g && E.actif ? " on" : "") + '" data-g="' + esc(g.id) + '" title="' + esc(g.libelle) + " · Alt+" + (i + 1) + '" aria-label="' + esc(g.libelle) + '">' + ico(g.icone) + pastille(g) + "</button>").join("");
    const urg = !!(E.idees && E.idees.urgent);
    $("#d19-btn-cass").classList.toggle("d19-idee", urg);
    $("#d19-btn-cass").classList.toggle("actif", E.panel);
    const vt = $("#d19-vtxt"); if (vt) vt.textContent = E.d.version || "19";
    const pg = E.d.groupes, aff = pg.length > 4 ? pg.slice(0, 4) : pg;
    const bt = (g) => '<button class="' + (g.id === E.g && E.actif ? "on" : "") + '" data-g="' + esc(g.id) + '" data-bas="1">' + ico(g.icone) + "<span>" + esc(g.libelle) + "</span>" + pastille(g) + "</button>";
    $("#d19-bas").innerHTML = aff.slice(0, 2).map(bt).join("") + '<button class="cent' + (E.panel ? " on" : "") + (urg ? " d19-idee" : "") + '" data-cbas="1" aria-label="Itare et Cassandra">' + ico("spark") + "</button>" + aff.slice(2).map(bt).join("")
      + (pg.length > 4 ? '<button class="' + (pg.slice(4).some((g) => g.id === E.g) ? "on" : "") + '" data-plus="1">' + ico("dots") + "<span>Plus</span></button>" : "");
  }

  // ── le rendu : colonne ─────────────────────────────────────────────────────
  function epinglesVisibles() {
    const d = E.d; if (!d) return [];
    return (d.epingles || []).filter((p) => d.groupes.some((g) => g.id === p.groupe && g.entrees.some((e) => e.id === p.entree)));
  }
  const nbDe = (n) => { const b = n.badge || {}; return b.n ? '<span class="d19-nb ' + (b.niveau || "") + '">' + b.n + "</span>" : (b.niveau ? '<span class="d19-nb ' + b.niveau + '">!</span>' : ""); };
  // ── la capsule : où je suis, et si quelque chose brûle (au-dessus de la colonne, dans l'espace libre sous la barre) ──
  const NIV = { danger: ["danger", "À traiter"], alerte: ["alerte", "À regarder"] };
  function rendreCapsule(rail) {
    const c = $("#d19-cap"); if (!c) return;
    const g = ent(), propre = !!(E.pageNom && !E.actif && E.fil);
    if (!E.d || (!g && !propre)) { c.style.display = "none"; return; }
    let niv = "", n = 0, lib, ic;
    if (propre) { niv = E.d.niveau || ""; lib = E.fil[1] || E.fil[0]; ic = g ? g.icone : "panorama"; }
    else {
      niv = g.niveau || ""; lib = g.libelle; ic = g.icone;
      g.entrees.forEach((e) => { n += (e.badge && e.badge.n) || 0; });
    }
    const [k, txt] = NIV[niv] || ["ok", "Tout va bien"];
    c.style.display = ""; c.className = "n-" + k + (rail ? " rail" : "");
    c.title = lib + " · " + (k === "ok" ? "tout est en ordre" : txt.toLowerCase() + (n ? " (" + n + ")" : "")) + " — cliquer pour voir";
    c.innerHTML = '<span class="ic">' + ico(ic) + '<i class="pt"></i></span><span class="tx"><b>' + esc(lib) + "</b><small>" + esc(k === "ok" ? txt : txt + (n ? " · " + n : "")) + "</small></span>";
  }
  function capsuleAller() {
    const g = ent(); if (!g || (E.pageNom && !E.actif)) { aller(E.g || (E.d.groupes[0] || {}).id, ""); return; }
    const e = g.entrees.find((x) => x.badge && (x.badge.niveau === "danger" || x.badge.niveau === "alerte")) || g.entrees[0];
    aller(g.id, e.id, "");
  }
  function rendreGauche() {
    const g = ent(), sd = $("#d19-side"); rendreCapsule(E.side === "rail" && !isPetit()); if (!g) { sd.innerHTML = ""; return; }
    const rail = E.side === "rail" && !isPetit();
    sd.classList.toggle("ferme", !E.side);
    sd.classList.toggle("rail", rail);
    $("#d19-scrim").classList.toggle("on", !!E.side && E.side !== "rail" && isPetit());
    if (E.lateral && E.pageNom) {                                       // la page a SA colonne (les familles de modules)
      const L = E.lateral;
      sd.innerHTML = L.items.map((i) => '<button class="d19-si ent' + (i.id === L.actif ? " on" : "") + '" data-lat="' + esc(i.id) + '" data-tip="' + esc(i.libelle) + '">' + ico(i.icone || "puzzle") + "<span>" + esc(i.libelle) + "</span>" + (i.n == null ? "" : '<span class="d19-nb">' + i.n + "</span>") + "</button>").join("");
      return;
    }
    let h = "";
    const ep = epinglesVisibles();
    if (ep.length) h += ep.map((p) => '<button class="d19-si pinned" data-tip="' + esc(p.libelle) + '" data-pg="' + esc(p.groupe) + '" data-pe="' + esc(p.entree) + '" data-pv="' + esc(p.vue || "") + '">' + ico("star") + "<span>" + esc(p.libelle) + "</span></button>").join("") + '<hr class="d19-sep">';
    const chev = (o) => ico("right", "car" + (o ? " ouv" : ""));
    for (const e of g.entrees) {
      const aEnfants = e.enfants.length > 0 || e.id === "flotte";
      const ouv = E.ouv.has(e.id) && aEnfants, actif = E.actif && E.e === e.id && E.g === g.id;
      h += '<button class="d19-si ent' + (actif && (!ouv || rail) ? " on" : "") + '" data-tip="' + esc(e.libelle) + '" data-e="' + esc(e.id) + '">' + ico(e.icone) + "<span>" + esc(e.libelle) + "</span>" + (!ouv ? nbDe(e) : "") + (aEnfants ? chev(ouv) : "") + "</button>";
      if (ouv) {
        if (e.id === "flotte") {
          h += rendreFlotteRail();
        } else {
          h += e.enfants.map((f) => {
            const vid = f.vue || f.id, etat = e.id === "panorama" && SECTIONS_ETAT.indexOf(vid) >= 0;
            return '<button class="d19-si sub' + (VUE_IC[vid] ? " ic" : "") + (actif && E.vue === vid ? " on" : "") + '" data-e="' + esc(e.id) + '" data-v="' + esc(vid) + '">' + (VUE_IC[vid] ? ico(VUE_IC[vid]) : etat ? '<span class="mx-dot" data-mdot="' + vid + '"></span>' : '<span class="pt"></span>') + "<span>" + esc(f.libelle) + "</span>" + (etat ? '<span class="mx-st" data-mst="' + vid + '"></span>' : "") + nbDe(f) + "</button>";
          }).join("");
        }
      }
    }
    sd.innerHTML = h;
    recopierEtatPanorama();
  }
  function fermerSide() { E.side = false; rendreGauche(); }

  // ── le rendu : bandeau de page / pastilles ────────────────────────────────
  const estPin = () => !!(E.d && (E.d.epingles || []).some((p) => p.cle === cleDe(E.g, E.e, E.vue)));
  // ── le fil d'Ariane : chaque niveau se visite, et chacun propose ses voisins ───────────────
  function crumbs() {
    const g = ent(), e = entree(), d = E.d;
    if (E.actif && g && e) {
      const vues = e.enfants || [], v = vues.find((f) => (f.vue || f.id) === E.vue);
      const c = [
        { l: g.libelle, ic: g.icone, go: () => aller(g.id, ""), sib: d.groupes.map((x) => ({ l: x.libelle, ic: x.icone, on: x.id === g.id, go: () => aller(x.id, "") })) },
        { l: e.libelle, go: () => aller(g.id, e.id, ""), sib: g.entrees.map((x) => ({ l: x.libelle, ic: x.icone, on: x.id === e.id, go: () => aller(g.id, x.id, "") })) },
      ];
      const premV = !vues.length || E.vue === (vues[0].vue || vues[0].id);
      c[1].ici = premV; c[0].ici = premV && e.id === g.entrees[0].id;       // viser ce niveau ne bougerait pas : « remonter » le saute
      if (E.vue) c.push({ l: v ? v.libelle : E.vue, go: null, sib: vues.map((f) => ({ l: f.libelle, on: (f.vue || f.id) === E.vue, go: () => aller(g.id, e.id, f.vue || f.id) })) });
      c[c.length - 1].cur = true;
      return c;
    }
    if (E.pageNom && E.fil) {
      const L = E.lateral, act = (id) => () => { if (E.pageAction) E.pageAction(id); };
      const c = [{ l: E.fil[0], go: () => window.switchTab("settings") }];
      if (E.fil.length > 1) c.push({ l: E.fil[1], go: L && E.pageAction ? act(L.items[0].id) : null });
      if (E.fil.length > 2) c.push({ l: E.fil[2], go: null, sib: L ? L.items.map((i) => ({ l: i.libelle, ic: i.icone, on: i.id === L.actif, go: act(i.id) })) : null });
      c[c.length - 1].cur = true;
      return c;
    }
    return [];
  }
  function remonter() { const c = E.crumbs || []; for (let i = c.length - 2; i >= 0; i--) if (c[i].go && !c[i].ici) { E.crMenu = null; c[i].go(); return; } }
  function rendreStrip() {
    const el = $("#d19-strip"), g = ent(), e = entree();
    const page = !!(E.d && E.pageNom && E.fil && !E.actif), norm = !!(E.d && g && e && E.actif);
    if (!page && !norm) { E.crumbs = []; el.innerHTML = ""; el.style.display = "none"; return; }
    el.style.display = "";
    const c = (E.crumbs = crumbs());
    const sep = '<span class="cr-sep" aria-hidden="true">' + ico("right") + "</span>";
    const peut = c.slice(0, -1).some((x) => x.go && !x.ici);
    const fil = '<nav class="fil" aria-label="Fil d’Ariane"><button class="cr-up" data-cr-up="1" title="Niveau supérieur (Alt + ↑)" aria-label="Niveau supérieur"' + (peut ? "" : " disabled") + ">" + ico("up") + "</button>"
      + c.map((x, i) => '<span class="cr-wrap">' + (x.cur ? '<span class="cr cur" aria-current="page">' + (x.ic ? ico(x.ic) : "") + esc(x.l) + "</span>" : '<button class="cr" data-cr="' + i + '">' + (x.ic ? ico(x.ic) : "") + esc(x.l) + "</button>")
        + (x.sib && x.sib.length > 1 ? '<button class="cr-c' + (E.crMenu === i ? " on" : "") + '" data-crm="' + i + '" aria-haspopup="true" aria-expanded="' + (E.crMenu === i) + '" aria-label="Autres pages de ce niveau" title="Autres pages de ce niveau">' + ico("down") + "</button>" : "")
        + (E.crMenu === i && x.sib ? '<div class="cr-menu" role="menu">' + x.sib.map((t, j) => '<button role="menuitem" class="' + (t.on ? "on" : "") + '" data-crs="' + i + "." + j + '">' + (t.ic ? ico(t.ic) : "") + esc(t.l) + "</button>").join("") + "</div>" : "")
        + "</span>").join(sep) + "</nav>";
    if (page) {
      el.innerHTML = fil + (E.lateral ? '<div class="pills" id="d19-pills">' + E.lateral.items.map((i) => '<button class="pl' + (i.id === E.lateral.actif ? " on" : "") + '" data-lat="' + esc(i.id) + '">' + esc(i.libelle) + "</button>").join("") + "</div>" : "");
    } else {
      el.innerHTML = fil + '<button class="pin' + (estPin() ? " on" : "") + '" data-pin="1" title="Épingler cette page" aria-label="Épingler cette page">' + ico("star") + "</button>"
        + '<button class="tit" data-ms="1" aria-label="Changer d’entrée">' + ico(e.icone) + "<span>" + esc(e.libelle) + "</span>" + ico("down") + "</button>"
        + '<div class="pills" id="d19-pills">' + e.enfants.map((f) => '<button class="pl' + (E.vue === (f.vue || f.id) ? " on" : "") + '" data-sx="' + esc(f.vue || f.id) + '">' + esc(f.libelle) + "</button>").join("") + "</div>";
    }
    const on = $(".pl.on", el), pc = $("#d19-pills");
    if (on && pc) pc.scrollLeft = Math.max(0, on.offsetLeft - 70);
  }
  function rendreMs() {
    const g = ent(); if (!g) return;
    const ep = epinglesVisibles();
    $("#d19-ms .box").innerHTML = (ep.length ? '<h3>Épinglés</h3><div class="pinrow">' + ep.map((p) => '<button class="d19-chip" data-mspin="1" data-pg="' + esc(p.groupe) + '" data-pe="' + esc(p.entree) + '" data-pv="' + esc(p.vue || "") + '">★ ' + esc(p.libelle) + "</button>").join("") + "</div>" : "")
      + "<h3>" + esc(g.libelle) + "</h3>" + g.entrees.map((e) => '<button class="row' + (E.actif && e.id === E.e ? " on" : "") + '" data-msen="' + esc(e.id) + '">' + ico(e.icone) + "<span>" + esc(e.libelle) + "</span><small>" + (e.badge && e.badge.n ? e.badge.n + " à voir · " : "") + (e.enfants.length ? e.enfants.length + " pages" : "") + "</small></button>").join("");
  }
  function ouvrirMs(v) { E.ms = v === undefined ? !E.ms : v; if (E.ms) { $("#d19-plus").classList.remove("ouvert"); rendreMs(); } $("#d19-ms").classList.toggle("ouvert", E.ms); }


  // ── l'interlocuteur du panneau ─────────────────────────────────────────────
  const NOMS = { itare: "Itare", cassandra: "Cassandra", inv: "Invités" };
  const autoMode = () => { const g = ent(); if (!E.d.cassandra_ok) return "itare"; return (g && g.interlocuteur === "itare") || !E.actif ? "itare" : "cassandra"; };
  const mode = () => (E.manual && !(E.manual === "cassandra" && !E.d.cassandra_ok) ? E.manual : autoMode());
  const heure = () => new Date().getHours();
  function ficheFil(m) { const k = pageCle(); return E.fils[m].find((f) => f.page === k) || null; }
  function filCourant(m) {
    const s = E.sel[m];
    if (s === "page") return ficheFil(m);
    if (s === "nouveau") return null;
    return E.fils[m].find((f) => f.fil === s) || null;
  }
  const labelFil = (m) => (E.sel[m] === "nouveau" ? "Nouveau fil" : E.sel[m] === "page" ? "Page en cours · " + (chemin().split(" › ").pop() || "") : ((filCourant(m) || {}).titre || "Fil"));

  async function chargerFils(m) {
    try { E.fils[m] = ((await agir("affichage.lire_fils", { agent: m })).fils) || []; } catch (e) { E.fils[m] = []; }
  }
  async function chargerMessages(fil, reprise) {
    if (!fil) return [];
    const dep = reprise ? (E.dernier[fil] || 0) : 0;
    try {
      const r = await agir("salon.lire", dep ? { fil, depuis: dep } : { fil, limite: 60 });
      const nv = r.messages || [];
      if (nv.length) { E.msgs[fil] = reprise ? (E.msgs[fil] || []).concat(nv) : nv; E.dernier[fil] = nv[nv.length - 1].id; return nv; }
      if (!reprise) E.msgs[fil] = [];
    } catch (e) {}
    return [];
  }
  async function assurerFil(m, texte) {
    let f = filCourant(m);
    if (f) return f.fil;
    const titre = E.sel[m] === "nouveau" ? (texte.length > 38 ? texte.slice(0, 36) + "…" : texte) : (chemin() || "Page");
    const c = await agir("salon.fil_creer", { titre: titre, terrain: m === "itare" ? "desk" : "" });
    const id = c.id;
    await agir("affichage.lier_fil", { fil: id, agent: m, page: E.sel[m] === "nouveau" ? "" : pageCle() });
    await chargerFils(m);
    if (E.sel[m] === "nouveau") E.sel[m] = id;
    return id;
  }
  async function envoyer(texte) {
    texte = String(texte || "").trim(); if (!texte) return;
    const m = mode();
    const dest = m === "inv" ? Array.from(E.invites).filter((a) => a !== "cassandra" || E.d.cassandra_ok) : [m];
    if (!dest.length) { toast("Personne n’est invité : choisis Itare ou Cassandra."); return; }
    E.sug = false; E.fmenu = false;
    try {
      const fil = await assurerFil(m, texte);
      await agir("salon.dire", { fil: fil, destinataires: dest, corps: texte });
      E.attente = Date.now() + 90000;
      await chargerMessages(fil, true);
      chargerFils(m).then(rendrePanel);
      rendrePanel(); sonder();
    } catch (e) { toast(e.message || "L’envoi a échoué."); rendrePanel(); }
  }
  let sondeT = null;
  function sonder() {
    clearTimeout(sondeT);
    if (!E.panel) return;
    sondeT = setTimeout(async function () {
      const m = mode(), f = filCourant(m);
      if (f) { const nv = await chargerMessages(f.fil, true); if (nv.length) rendrePanel(); }
      sonder();
    }, 2500);
  }

  // ── les idées ──────────────────────────────────────────────────────────────
  let ideesT = null;
  function idees(maintenant) {
    clearTimeout(ideesT);
    ideesT = setTimeout(async function () {
      if (!E.d) return;
      try {
        const g = ent(), e = entree();
        E.idees = await agir("affichage.lire_idees", { mode: mode() === "inv" ? "" : mode(), groupe: g ? g.id : "", entree: e ? e.id : "", sous: E.vue, page: chemin(), heure: heure(), faits: Array.from(E.faits), refuses: Array.from(E.refuses) });
        rendreHaut(); if (E.panel) rendrePanel();
      } catch (er) {}
    }, maintenant ? 0 : 400);
  }

  // ── le rendu : panneau ─────────────────────────────────────────────────────
  function carteActe(a, i) {
    const m = a.meta || {};
    let h = '<div class="acte"><h4>' + esc(m.titre || a.cle) + '<span class="d19-pill' + (m.risque === "lecture" ? "" : " alerte") + '">risque ' + esc(m.risque || "") + "</span></h4><dl><dt>Périmètre</dt><dd>" + esc(m.perimetre || "") + "</dd><dt>Preuve</dt><dd>" + esc(m.preuve || "") + "</dd><dt>Retour</dt><dd>" + esc(m.retour || "") + "</dd></dl>";
    if (a.etat === "propose") h += (m.risque !== "lecture" ? '<label><input type="checkbox" id="d19-ck' + i + '"> Je confirme ce geste</label>' : "") + '<div class="bt"><button class="d19-btn" data-valider="' + i + '">Valider</button><button class="d19-btn sec" data-refuser="' + i + '">Refuser</button></div>';
    else if (a.etat === "fait") h += '<p class="fait">Fait. ' + esc(a.resume || "") + "</p>";
    else if (a.etat === "echec") h += "<p>Refusé par le serveur : " + esc(a.resume || "") + "</p>";
    else h += "<p>Refusé. Rien n’a été fait.</p>";
    return h + "</div>";
  }
  function menuFils(m) {
    const sel = E.sel[m], rec = E.fils[m];
    return '<div class="fmenu"><button class="fi' + (sel === "page" ? " on" : "") + '" data-fpage="1"><span>' + (sel === "page" ? "✓ " : "") + "Page en cours</span><small>" + esc(chemin() || "—") + "</small></button>"
      + '<button class="fi nouv" data-fnew="1">' + ico("plus") + "Nouveau fil</button><h4>Fils récents avec " + esc(NOMS[m]) + "</h4>"
      + (rec.length ? rec.map((f) => '<button class="fi' + (sel === f.fil ? " on" : "") + '" data-fth="' + f.fil + '"><span>' + (sel === f.fil ? "✓ " : "") + esc(f.titre) + "</span><small>" + esc(quand(f.dernier)) + " · " + f.n + " message" + (f.n > 1 ? "s" : "") + (f.page ? " · page" : "") + "</small></button>").join("") : '<div class="intro">Aucun fil pour l’instant.</div>') + "</div>";
  }
  function quand(ts) { if (!ts) return ""; const s = (Date.now() / 1000) - ts; if (s < 60) return "à l’instant"; if (s < 3600) return Math.round(s / 60) + " min"; if (s < 86400) return Math.round(s / 3600) + " h"; return Math.round(s / 86400) + " j"; }
  const INTRO = { itare: "Je m’occupe de ton poste de travail : journée, courrier, tâches, documents. Je travaille avec les réglages de ton compte.", cassandra: "Je veille sur le parc. Dis-moi ce que tu veux regarder ou faire ; chaque acte montre sa preuve et son retour.", inv: "Fil à plusieurs : invite Itare ou Cassandra, puis écris." };
  function rendrePanel() {
    if (!E.d) return;
    const m = mode(), f = filCourant(m), msgs = f ? (E.msgs[f.fil] || []) : [];
    const moi = "humain:" + E.compte;
    const reg = m === "itare" ? '<div class="reg"><b>Réglé par ton compte :</b> modèle, mémoire, ton et accès.</div>' : m === "cassandra" ? '<div class="reg"><b>Tout le parc.</b> Elle propose, tu valides. Administrateur seulement.</div>' : '<div class="reg"><b>Fil à plusieurs.</b> Invite Itare ou Cassandra : chacun répond avec ses propres accès.</div>';
    const qui = m === "inv" ? '<div class="qui">' + ["itare"].concat(E.d.cassandra_ok ? ["cassandra"] : []).map((a) => '<button class="d19-chip' + (E.invites.has(a) ? " on" : "") + '" data-inv="' + a + '">' + (E.invites.has(a) ? "✓ " : "+ ") + esc(NOMS[a]) + "</button>").join("") + "</div>" : "";
    const id = E.idees || { idees: [], actes: {} };
    const idl = m === "inv" ? [] : (id.idees || []);
    const locaux = E.actes[m];
    const corps = (msgs.length || locaux.length) ? msgs.map((x) => '<div class="m' + (x.auteur === moi ? " moi" : "") + '">' + (x.auteur === moi ? "" : '<span class="au">' + esc(NOMS[x.auteur] || String(x.auteur).replace(/^humain:/, "")) + "</span>") + esc(x.corps) + "</div>").join("") + locaux.map(carteActe).join("")
      : '<div class="intro">' + esc(INTRO[m]) + "</div>";
    const encours = E.attente > Date.now() && msgs.length && msgs[msgs.length - 1].auteur === moi;
    $("#d19-cass .in").innerHTML = '<div class="d19-poignee" data-poignee="1"></div><header><div class="who"><span class="av2">' + (m === "itare" ? "I" : m === "cassandra" ? "C" : "+") + "</span><div><b>" + esc(NOMS[m]) + '</b><button class="fsel' + (E.fmenu ? " on" : "") + '" data-fsel="1" aria-label="Choisir le fil"><span>' + esc(labelFil(m)) + "</span>" + ico("down") + "</button></div></div>"
      + '<button class="d19-ib info" data-reg="1" aria-label="Réglages de cet interlocuteur">' + ico("info") + '</button><button class="d19-ib" data-cclose="1" aria-label="Fermer">' + ico("close") + "</button></header>"
      + '<div class="modes" role="tablist"><button data-mode="itare" class="' + (m === "itare" ? "on" : "") + '">Itare</button><button data-mode="cassandra" class="' + (m === "cassandra" ? "on" : "") + '"' + (E.d.cassandra_ok ? "" : ' disabled title="Réservé à l’administrateur"') + '>Cassandra</button><button data-mode="inv" class="' + (m === "inv" ? "on" : "") + '">Invités</button><span class="auto">' + (E.manual ? "manuel" : "auto") + "</span></div>"
      + (E.fmenu ? menuFils(m) : "") + reg.replace('class="reg"', 'class="reg' + (E.regOuvert ? " ouvert" : "") + '"') + qui
      + '<div class="msgs" id="d19-msgs">' + corps + (encours ? '<div class="attente">' + esc(NOMS[m === "inv" ? "itare" : m]) + " réfléchit…</div>" : "") + "</div>"
      + '<div class="sug' + (E.sug ? " ouvert" : "") + '"><div class="sughead">Idées pour cette page <i>· en direct</i></div>' + (idl.length ? idl.map((x) => x.genre === "acte" ? '<button class="idee act" data-idee-acte="' + esc(x.id) + '"><span>✦ ' + esc(x.titre) + "</span><small>" + esc(x.raison || "") + (x.risque ? " · risque " + esc(x.risque) : "") + "</small></button>" : '<button class="idee" data-idee-q="' + esc(x.id) + '"><span>' + esc(x.titre) + "</span>" + (x.raison ? "<small>" + esc(x.raison) + "</small>" : "") + "</button>").join("") : '<div class="vide">Rien à proposer pour l’instant.</div>') + "</div>"
      + '<form id="d19-f"><button type="button" class="d19-ib d19-sugbtn' + (E.sug ? " on" : "") + '" data-sug="1" aria-label="Idées et gestes">' + ico("spark") + '</button><input id="d19-in" placeholder="' + (m === "inv" ? "Écrire au fil…" : "Demander à " + esc(NOMS[m]) + "…") + '" autocomplete="off" value="' + esc(E.brouillon) + '"><button class="d19-btn">Envoyer</button></form>';
    const mm = $("#d19-msgs"); if (mm) mm.scrollTop = mm.scrollHeight;
  }
  async function ouvrirPanel(v) {
    const avant = E.panel; E.panel = v === undefined ? !E.panel : v; if (E.panel === avant) return;
    $("#d19-cass").classList.toggle("ouvert", E.panel);
    $("#d19-btn-cass").classList.toggle("actif", E.panel);
    if (E.panel) {
      E.sideAvant = E.side; E.sideTouche = false;
      if (!isPetit() && E.w !== "xl") { E.side = "rail"; rendreGauche(); }
      ouvrirMs(false); rendrePanel();
      const m = mode(); await chargerFils(m); const f = filCourant(m); if (f) await chargerMessages(f.fil); rendrePanel(); idees(true); sonder();
    } else if (!isPetit() && !E.sideTouche && E.w !== "xl") { E.side = E.sideAvant; rendreGauche(); }
    rendreHaut();
  }
  async function changerMode(m) { E.manual = m; E.fmenu = false; E.sug = false; await chargerFils(m); const f = filCourant(m); if (f && !E.msgs[f.fil]) await chargerMessages(f.fil); rendrePanel(); idees(true); }

  // ── la palette ─────────────────────────────────────────────────────────────
  let palRes = [], palSel = 0;
  function indexPal() {
    const r = [];
    (E.d.groupes || []).forEach((g) => g.entrees.forEach((e) => { r.push({ g: g.id, e: e.id, v: "", l: g.libelle + " › " + e.libelle, ic: e.icone }); e.enfants.forEach((f) => r.push({ g: g.id, e: e.id, v: f.vue || f.id, l: g.libelle + " › " + e.libelle + " › " + f.libelle, ic: e.icone })); }));
    (E.d.avatar || []).forEach((a) => r.push({ av: a.id, l: "Paramètres › " + a.libelle, ic: a.icone || "info" }));
    Object.keys((E.idees && E.idees.actes) || {}).forEach((k) => r.push({ act: k, l: "Action › " + E.idees.actes[k].titre, ic: "spark" }));
    return r;
  }
  function palRender() {
    const q = ($("#d19-pal-in").value || "").trim().toLowerCase();
    palRes = q ? indexPal().filter((x) => x.l.toLowerCase().includes(q)).slice(0, 30) : E.rec.map((r) => ({ g: r.g, e: r.e, v: r.v, l: r.l, ic: "clock", rec: 1 }));
    palSel = Math.min(palSel, Math.max(0, palRes.length - 1));
    $("#d19-pal .res").innerHTML = palRes.map((x, i) => '<button class="' + (i === palSel ? "sel" : "") + '" data-pi="' + i + '">' + ico(x.ic) + esc(x.l) + (x.rec ? "<small>récent</small>" : x.act ? "<small>acte</small>" : "") + "</button>").join("") || '<div style="padding:14px;color:var(--txt-faint)">Aucune page ne correspond.</div>';
  }
  function palOuvrir() { fermerPops(); $("#d19-pal").classList.add("ouvert"); $("#d19-pal-in").value = ""; palSel = 0; palRender(); setTimeout(() => $("#d19-pal-in").focus(), 0); }
  const palFermer = () => $("#d19-pal").classList.remove("ouvert");
  function palChoisir(i) {
    const x = palRes[i]; if (!x) return; palFermer();
    if (x.act) { ouvrirPanel(true); proposerActe(E.idees.idees.find((y) => y.acte === x.act) || { acte: x.act, cible: "" }); }
    else if (x.av) { const a = (E.d.avatar || []).find((y) => y.id === x.av); if (a) { marquerPage(a); ouvrirNoeud(a); } }
    else aller(x.g, x.e, x.v);
  }

  // ── les actes ──────────────────────────────────────────────────────────────
  function proposerActe(idee) {
    const m = mode() === "inv" ? "cassandra" : mode(); E.manual = m;
    const meta = (E.idees.actes || {})[idee.acte];
    if (!meta) { toast("Ce geste n’est pas proposé ici."); return; }
    E.actes[m].push({ cle: idee.acte, cible: idee.cible || "", meta: meta, etat: "propose" });
    E.sug = false; rendrePanel();
  }
  async function validerActe(i) {
    const m = mode(), a = E.actes[m][i], meta = a.meta;
    if (meta.risque !== "lecture") { const ck = $("#d19-ck" + i); if (!ck || !ck.checked) { toast("Coche « Je confirme » pour valider ce geste."); return; } }
    try {
      const args = {}; args[meta.arg] = a.cible;
      const r = await agir(meta.capacite, args);
      a.etat = "fait"; a.resume = typeof r === "object" ? JSON.stringify(r).slice(0, 160) : String(r || "");
      E.faits.add(a.cle);
    } catch (e) { a.etat = "echec"; a.resume = e.message; }
    rendrePanel(); idees(true);
  }

  // ── les épingles ───────────────────────────────────────────────────────────
  async function basculerPin() {
    const e = entree(), g = ent(); if (!e || !g) return;
    const k = cleDe(g.id, e.id, E.vue);
    try {
      if (estPin()) await agir("affichage.desepingler", { cle: k });
      else await agir("affichage.epingler", { cle: k, groupe: g.id, entree: e.id, vue: E.vue, libelle: ((e.enfants.find((f) => (f.vue || f.id) === E.vue) || {}).libelle || e.libelle) + (E.vue ? " · " + e.libelle : "") });
      await charger(); toast(estPin() ? "Page épinglée en haut de la colonne." : "Épingle retirée.");
    } catch (er) { toast(er.message); }
  }

  // ── le menu de l'avatar : celui de l'ancienne interface, complété ──────────
  // l'apparence : un thème (icônes) et un habillage (noms), à la place des initiales de l'ancien sélecteur
  function themeActuel() { const r = document.documentElement; return r.getAttribute("data-habillage") || r.getAttribute("data-theme") || "light"; }
  function blocApparence() {
    const etats = (typeof TH_ETATS !== "undefined" ? TH_ETATS : []), hab = CASS.habillages || {};
    const racine = document.documentElement, courant = racine.getAttribute("data-habillage") || "", base = racine.getAttribute("data-theme") || "light";
    const bases = etats.filter((x) => !hab[x[0]]);
    const themes = bases.map((x) => '<button type="button" role="radio" aria-checked="' + (!courant && (x[0] === base || (x[0] === "auto" && !racine.getAttribute("data-theme"))) ? "true" : "false") + '" data-d19-theme="' + esc(x[0]) + '" title="' + esc(x[1]) + '" aria-label="' + esc(x[1]) + '">' + x[2] + "</button>").join("");
    const habs = ['<button type="button" class="d19-chip' + (!courant ? " on" : "") + '" data-d19-hab="">Cassandra</button>'].concat(Object.keys(hab).map((id) => '<button type="button" class="d19-chip' + (courant === id ? " on" : "") + '" data-d19-hab="' + esc(id) + '">' + esc(hab[id].libelle || id) + "</button>")).join("");
    return '<div class="um-h">Thème</div><div class="d19-themes" role="radiogroup" aria-label="Thème">' + themes + '</div><div class="um-h" style="margin-top:10px">Habillage</div><div class="d19-habs">' + habs + "</div>";
  }
  function completerAvatar() {
    const um = $("#usermenu"); if (!um) return;
    $$("[data-d19-av]", um).forEach((x) => x.remove());
    const seg = $("#um-seg", um), ancien = seg && seg.closest(".um-sec");
    if (ancien) ancien.style.display = "none";                       // l'ancien sélecteur (initiales) cède la place
    const hote = $(".um-acts", um); if (!hote) return;
    const app = document.createElement("div"); app.className = "um-sec"; app.setAttribute("data-d19-av", "1"); app.innerHTML = blocApparence();
    const acts = document.createElement("div"); acts.className = "um-acts"; acts.setAttribute("data-d19-av", "1");
    acts.innerHTML = (E.d.avatar || []).map((a) => '<button class="um-i" role="menuitem" data-d19-avid="' + esc(a.id) + '">' + ico(a.icone || "info") + esc(a.libelle) + "</button>").join("")
      ;
    hote.parentNode.insertBefore(app, hote); hote.parentNode.insertBefore(acts, hote);
    // « Info Cassandra » : tout en bas, à côté du numéro de version
    const pied = $(".um-pied", um);
    if (pied) { const v = pied.querySelector(".bu-sp"); const b = document.createElement("button"); b.type = "button"; b.className = "d19-info-lien"; b.setAttribute("data-d19-av", "1"); b.setAttribute("data-d19-info", "1"); b.textContent = "Info Cassandra ›"; pied.insertBefore(b, v ? v.nextSibling : null); }
  }

  // ── les pages propres : Société / Organisation, Info Cassandra ─────────────
  function redimensionner(fichier, fin, carre) {
    const r = new FileReader();
    r.onload = function () {
      const img = new Image();
      img.onload = function () {
        const c = document.createElement("canvas");
        if (carre) {                                                       // le logo carré : recadré au centre, 128 px
          const cote = Math.min(img.width, img.height); c.width = c.height = 128;
          c.getContext("2d").drawImage(img, (img.width - cote) / 2, (img.height - cote) / 2, cote, cote, 0, 0, 128, 128);
        } else {
          const t = Math.min(1, 256 / Math.max(img.width, img.height));
          c.width = Math.max(1, Math.round(img.width * t)); c.height = Math.max(1, Math.round(img.height * t));
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        }
        let u = c.toDataURL("image/png"); if (u.length > 170000) u = c.toDataURL("image/jpeg", 0.85);
        fin(u.length <= 175000 ? u : "");
      };
      img.onerror = () => fin("");
      img.src = r.result;
    };
    r.readAsDataURL(fichier);
  }
  // ── une page de l'ancienne interface, rangée en rubriques dans la colonne de gauche ──────────
  function appliquerCoffre(id) {
    const g = (i) => document.getElementById(i);
    const etat = document.querySelector("#tab-vault .cf-state"), porte = document.querySelector("#tab-vault .cf-gate"), onb = g("cf-onboard"), jr = g("cf-audit") && g("cf-audit").closest(".card");
    if (typeof window.cfVue === "function") window.cfVue(id === "coffre" ? "cf-v-secrets" : "cf-v-accueil");
    if (id === "coffre") return;
    if (!g("d19-gen")) {                                              // l'outil neuf : un générateur de mot de passe, tiré dans le navigateur
      const host = onb && onb.parentNode, c = document.createElement("section");
      c.className = "card"; c.id = "d19-gen";
      c.innerHTML = '<div class="card-title">Générateur de mot de passe</div><div class="d19-gen"><div class="sortie"><input type="text" id="d19-gen-sortie" readonly aria-label="Mot de passe généré"><button type="button" class="d19-btn sec" data-gen-copier="1">Copier</button><button type="button" class="d19-btn" data-gen-nouveau="1">Générer</button></div>'
        + '<label>Longueur : <b id="d19-gen-n">20</b><input type="range" id="d19-gen-long" min="8" max="64" value="20"></label><div class="choix"><label><input type="checkbox" id="d19-gen-maj" checked> Majuscules</label><label><input type="checkbox" id="d19-gen-min" checked> Minuscules</label><label><input type="checkbox" id="d19-gen-chi" checked> Chiffres</label><label><input type="checkbox" id="d19-gen-sym" checked> Symboles</label></div>'
        + '<p class="cf-note">Tiré dans ton navigateur, avec le hasard du système : rien n’est envoyé ni enregistré.</p></div>';
      (host || document.querySelector("#tab-vault .cf-page")).appendChild(c);
      genererMdp();
    }
    const aff = (e, v) => { if (e) e.style.display = v ? "" : "none"; };
    aff(etat, id === "tableau"); aff(porte, id === "tableau"); aff(onb, id === "outils"); aff(g("d19-gen"), id === "outils"); aff(jr, id === "rapport");
  }
  function genererMdp() {
    const n = +document.getElementById("d19-gen-long").value, jeux = [["d19-gen-maj", "ABCDEFGHJKLMNPQRSTUVWXYZ"], ["d19-gen-min", "abcdefghijkmnopqrstuvwxyz"], ["d19-gen-chi", "23456789"], ["d19-gen-sym", "!#$%&*+-=?@^_"]]
      .filter((x) => document.getElementById(x[0]).checked);
    document.getElementById("d19-gen-n").textContent = n;
    const sortie = document.getElementById("d19-gen-sortie");
    if (!jeux.length) { sortie.value = ""; return; }
    const tous = jeux.map((x) => x[1]).join(""), alea = (m) => { const b = new Uint32Array(1); let v; do { crypto.getRandomValues(b); v = b[0]; } while (v >= 4294967296 - (4294967296 % m)); return v % m; };
    const c = jeux.map((x) => x[1][alea(x[1].length)]);                  // au moins un caractère de chaque jeu choisi
    while (c.length < n) c.push(tous[alea(tous.length)]);
    for (let i = c.length - 1; i > 0; i--) { const j = alea(i + 1); [c[i], c[j]] = [c[j], c[i]]; }
    sortie.value = c.slice(0, n).join("");
  }
  const PAGES_V18 = {
    vault: { titre: "Mon coffre-fort", appliquer: appliquerCoffre,
      items: [{ id: "tableau", libelle: "Tableau de bord", icone: "panorama" }, { id: "coffre", libelle: "Coffre", icone: "lock" }, { id: "outils", libelle: "Outils", icone: "key" }, { id: "rapport", libelle: "Rapport", icone: "scroll" }] },
  };
  function entrerPageV18(nom, pg) {
    E.rubV18 = E.rubV18 || {}; E.actif = null; E.hors = nom; E.pageNom = nom;
    majPageV18(nom, pg, E.rubV18[nom] || pg.items[0].id);
  }
  function majPageV18(nom, pg, rub) {
    E.rubV18[nom] = rub;
    E.fil = ["Paramètres", pg.titre, (pg.items.find((i) => i.id === rub) || {}).libelle || rub];
    E.lateral = { titre: pg.titre, actif: rub, items: pg.items };
    E.pageAction = (id) => majPageV18(nom, pg, id);
    pg.appliquer(rub); rendre();
  }
  // ── une page propre : son onglet, son fil d'Ariane ────────────────────────
  function marquerPage(a) {
    E.pageNom = a.ecran && CASS.nomOnglet ? CASS.nomOnglet(a.ecran) : "";
    E.fil = ["Paramètres", a.id === "menus:modules" ? "Modules et Applications" : a.libelle]; E.lateral = null;
  }
  async function ouvrirModules(fam) {
    E.famModules = fam || "tous"; marquerPage({ id: "menus:modules", ecran: "menus:vue_modules", libelle: "Modules et Applications" });
    CASS.ouvrirEcran("menus:vue_modules", "Modules et Applications");
  }
  // ── Société / Organisation : quatre rubriques, chacune un tableau ──────────
  const PAYS = "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split(" ");
  const DEPTS = "01 Ain|02 Aisne|03 Allier|04 Alpes-de-Haute-Provence|05 Hautes-Alpes|06 Alpes-Maritimes|07 Ardèche|08 Ardennes|09 Ariège|10 Aube|11 Aude|12 Aveyron|13 Bouches-du-Rhône|14 Calvados|15 Cantal|16 Charente|17 Charente-Maritime|18 Cher|19 Corrèze|2A Corse-du-Sud|2B Haute-Corse|21 Côte-d’Or|22 Côtes-d’Armor|23 Creuse|24 Dordogne|25 Doubs|26 Drôme|27 Eure|28 Eure-et-Loir|29 Finistère|30 Gard|31 Haute-Garonne|32 Gers|33 Gironde|34 Hérault|35 Ille-et-Vilaine|36 Indre|37 Indre-et-Loire|38 Isère|39 Jura|40 Landes|41 Loir-et-Cher|42 Loire|43 Haute-Loire|44 Loire-Atlantique|45 Loiret|46 Lot|47 Lot-et-Garonne|48 Lozère|49 Maine-et-Loire|50 Manche|51 Marne|52 Haute-Marne|53 Mayenne|54 Meurthe-et-Moselle|55 Meuse|56 Morbihan|57 Moselle|58 Nièvre|59 Nord|60 Oise|61 Orne|62 Pas-de-Calais|63 Puy-de-Dôme|64 Pyrénées-Atlantiques|65 Hautes-Pyrénées|66 Pyrénées-Orientales|67 Bas-Rhin|68 Haut-Rhin|69 Rhône|70 Haute-Saône|71 Saône-et-Loire|72 Sarthe|73 Savoie|74 Haute-Savoie|75 Paris|76 Seine-Maritime|77 Seine-et-Marne|78 Yvelines|79 Deux-Sèvres|80 Somme|81 Tarn|82 Tarn-et-Garonne|83 Var|84 Vaucluse|85 Vendée|86 Vienne|87 Haute-Vienne|88 Vosges|89 Yonne|90 Territoire de Belfort|91 Essonne|92 Hauts-de-Seine|93 Seine-Saint-Denis|94 Val-de-Marne|95 Val-d’Oise|971 Guadeloupe|972 Martinique|973 Guyane|974 La Réunion|976 Mayotte".split("|");
  const nomPays = (c) => { try { return new Intl.DisplayNames(["fr"], { type: "region" }).of(c) || c; } catch (e) { return c; } };
  const nomDevise = (c) => { try { return new Intl.DisplayNames(["fr"], { type: "currency" }).of(c) || c; } catch (e) { return c; } };
  const devises = () => { let l = []; try { l = Intl.supportedValuesOf("currency"); } catch (e) {} return l.length ? l : ["EUR", "USD", "GBP", "CHF", "CAD", "JPY"]; };
  const CH_ORG = [["raison_sociale", "Raison sociale", "text"], ["devise", "Devise principale", "devise"], ["pays", "Pays", "pays"], ["adresse", "Adresse", "area"], ["code_postal", "Code postal", "court"],
    ["ville", "Ville", "text"], ["departement", "Département / Canton", "dept"], ["telephone", "Téléphone", "tel"], ["mobile", "Tél portable", "tel"], ["fax", "Fax", "tel"], ["email", "Email", "email"],
    ["web", "Web", "url"], ["code_barres", "Code-barres", "text"], ["logo", "Logo", "image"], ["logo_carre", "Logo (carré)", "image"], ["note", "Note", "area"]];
  const CH_ST = [["raison_sociale", "Raison sociale", "text"], ["adresse", "Adresse", "area"], ["code_postal", "Code postal", "court"], ["ville", "Ville", "text"], ["pays", "Pays", "pays"], ["departement", "Département / Canton", "dept"],
    ["telephone", "Téléphone", "tel"], ["email", "Email", "email"], ["web", "Web", "url"], ["siren", "Id. prof. 1 (SIREN)", "text"], ["code_comptable", "Code comptable", "text"], ["note", "Note", "area"]];
  const RESEAUX = [["facebook", "Facebook"], ["instagram", "Instagram"], ["linkedin", "Linkedin"], ["skype", "Skype"], ["snapchat", "Snapchat"], ["twitter", "Twitter"], ["whatsapp", "Whatsapp"], ["youtube", "Youtube"]];
  const JOURS = [["lundi", "Lundi"], ["mardi", "Mardi"], ["mercredi", "Mercredi"], ["jeudi", "Jeudi"], ["vendredi", "Vendredi"], ["samedi", "Samedi"], ["dimanche", "Dimanche"]];
  const ST = [["comptabilite", "Fournisseur du service de Comptabilité", "archive"], ["informatique", "Fournisseur informatique", "fleet"]];
  const RUBRIQUES = [{ id: "organisation", libelle: "Mon organisation", icone: "building" }, { id: "reseaux", libelle: "Réseaux sociaux", icone: "globe" },
    { id: "heures", libelle: "Heures d’ouverture", icone: "clock" }, { id: "soustraitants", libelle: "Sous-traitants", icone: "puzzle" }];
  function controle(id, type, v) {
    v = v == null ? "" : v;
    if (type === "area") return '<textarea id="' + id + '" rows="3">' + esc(v) + "</textarea>";
    if (type === "pays") return '<select id="' + id + '"><option value=""></option>' + PAYS.map((c) => [c, nomPays(c)]).sort((a, b) => a[1].localeCompare(b[1], "fr")).map((x) => '<option value="' + x[0] + '"' + (x[0] === v ? " selected" : "") + ">" + esc(x[1]) + "</option>").join("") + "</select>";
    if (type === "devise") return '<select id="' + id + '"><option value=""></option>' + devises().map((c) => '<option value="' + c + '"' + (c === v ? " selected" : "") + ">" + c + " — " + esc(nomDevise(c)) + "</option>").join("") + "</select>";
    if (type === "dept") return '<input type="text" id="' + id + '" value="' + esc(v) + '" list="' + id + '-l" autocomplete="off"><datalist id="' + id + '-l">' + DEPTS.map((d) => '<option value="' + esc(d.slice(d.indexOf(" ") + 1)) + '">' + esc(d) + "</option>").join("") + "</datalist>";
    const t = type === "email" ? "email" : type === "url" ? "url" : "text";
    return '<input type="' + t + '" id="' + id + '" value="' + esc(v) + '" autocomplete="off"' + (type === "court" ? ' class="court"' : "") + ">";
  }
  const tableau = (titre, lignes) => '<div class="d19-tbl"><table><thead><tr><th colspan="2">' + esc(titre) + "</th></tr></thead><tbody>" + lignes + "</tbody></table></div>";
  const sauve = (cle) => '<p class="d19-sauve"><button type="button" class="d19-btn grand" data-sauve="' + cle + '">Enregistrer</button><span class="d19-msg" data-msg="' + cle + '"></span></p>';
  async function pageSociete(corps, rub) {
    rub = RUBRIQUES.some((r) => r.id === rub) ? rub : (E.rubSociete || "organisation");
    E.rubSociete = rub;
    const nom = RUBRIQUES.find((r) => r.id === rub).libelle;
    E.pageNom = CASS.nomOnglet("affichage:vue_societe"); E.fil = ["Paramètres", "Société / Organisation", nom];
    E.lateral = { titre: "Société / Organisation", actif: rub, items: RUBRIQUES.map((r) => ({ id: r.id, libelle: r.libelle, icone: r.icone })) };
    E.pageAction = (id) => pageSociete(corps, id);
    const sc = corps.closest(".sh-scene"), t = sc && sc.querySelector(".sh-titre");
    if (t) {
      t.textContent = "Société / Organisation";
      let l = sc.querySelector(".sh-legende"); if (!l) { l = document.createElement("p"); l.className = "sh-legende"; t.after(l); }
      l.textContent = "Modifiez les informations de votre société ou organisation. Cliquez sur « Enregistrer » en bas de la rubrique pour sauvegarder.";
    }
    let o; try { o = await agir("affichage.lire_organisation", {}); } catch (e) { corps.innerHTML = '<div class="empty-state">' + esc(e.message) + "</div>"; rendre(); return; }
    if (!o.complet) { corps.innerHTML = '<div class="empty-state">Ces informations se règlent par un administrateur.</div>'; rendre(); return; }
    const images = { logo: o.organisation.logo || "", logo_carre: o.organisation.logo_carre || "" };
    let h = "";
    if (rub === "organisation") {
      h = tableau("Société / Organisation", CH_ORG.map(([c, lib, type]) => "<tr><td class=\"l\">" + esc(lib) + "</td><td>" + (type === "image"
        ? '<div class="d19-logozone"><span class="d19-apercu' + (c === "logo_carre" ? " carre" : "") + '" id="o-ap-' + c + '"></span><label class="d19-btn sec" for="o-' + c + '" style="cursor:pointer">Choisir une image…</label><input type="file" id="o-' + c + '" accept="image/png,image/jpeg,image/webp,image/gif" hidden><button type="button" class="d19-btn sec" data-retire="' + c + '">Retirer</button></div>'
        : controle("o-" + c, type, o.organisation[c])) + "</td></tr>").join("")) + sauve("organisation");
    } else if (rub === "reseaux") {
      h = '<p class="d19-aide">Les identifiants et adresses de vos pages. Ils s’affichent ici ; les modules qui en ont besoin les reprennent.</p><div class="d19-tbl"><table><thead><tr><th>Réseaux sociaux</th><th>ID du réseau social</th><th>Url</th><th></th></tr></thead><tbody>'
        + RESEAUX.map(([r, lib]) => { const d = o.reseaux[r] || { id: "", url: "" }; return '<tr><td class="l">' + esc(lib) + '</td><td><input type="text" id="r-' + r + '-id" value="' + esc(d.id) + '" autocomplete="off"></td><td><input type="url" id="r-' + r + '-url" value="' + esc(d.url) + '" autocomplete="off"></td><td class="lien">' + (d.url ? '<a href="' + esc(d.url) + '" target="_blank" rel="noopener noreferrer">' + esc(d.id || d.url) + "</a>" : esc(d.id)) + "</td></tr>"; }).join("")
        + "</tbody></table></div>" + sauve("reseaux");
    } else if (rub === "heures") {
      h = '<p class="d19-aide">Entrez ici les heures d’ouverture régulières de votre organisation.</p><div class="d19-tbl"><table><thead><tr><th>Jour</th><th>Valeur</th></tr></thead><tbody>'
        + JOURS.map(([j, lib]) => '<tr><td class="l">' + lib + ' <span class="d19-i" title="Par exemple : 9h-12h / 14h-18h, ou : fermé">i</span></td><td><input type="text" id="h-' + j + '" value="' + esc(o.heures[j]) + '" autocomplete="off" placeholder="ex. 9h-18h"></td></tr>').join("") + "</tbody></table></div>" + sauve("heures");
    } else {
      h = '<p class="d19-aide">Si la gestion de votre application est sous-traitée à des prestataires externes (un comptable ou expert-comptable, un prestataire informatique), saisissez ici leurs informations afin qu’elles ne soient pas perdues en cas de remplacement de l’administrateur.</p>'
        + ST.map(([k, lib, ic]) => '<h3 class="d19-st">' + ico(ic) + esc(lib) + "</h3>" + tableau("Société / Organisation", CH_ST.map(([c, l, type]) => '<tr><td class="l">' + esc(l) + "</td><td>" + controle("s-" + k + "-" + c, type, o.soustraitants[k][c]) + "</td></tr>").join("")) + sauve("st:" + k)).join("");
    }
    corps.innerHTML = '<div class="d19-societe">' + h + "</div>";
    const val = (id) => { const e = document.getElementById(id); return e ? e.value : ""; };
    const aper = (c) => { const e = document.getElementById("o-ap-" + c); if (e) { e.style.backgroundImage = images[c] ? "url(" + images[c] + ")" : ""; e.innerHTML = images[c] ? "" : TOIT; } };
    if (rub === "organisation") {
      ["logo", "logo_carre"].forEach((c) => {
        aper(c);
        const f = document.getElementById("o-" + c);
        f.addEventListener("change", (ev) => { const fi = ev.target.files && ev.target.files[0]; if (fi) redimensionner(fi, (u) => { if (!u) { toast("Image trop lourde ou illisible."); return; } images[c] = u; aper(c); }, c === "logo_carre"); });
      });
      $$("[data-retire]", corps).forEach((b) => b.addEventListener("click", () => { images[b.dataset.retire] = ""; aper(b.dataset.retire); }));
    }
    $$("[data-sauve]", corps).forEach((b) => b.addEventListener("click", async () => {
      const cle = b.dataset.sauve; let section, valeurs = {};
      if (cle === "organisation") { section = "organisation"; CH_ORG.forEach(([c, , type]) => { valeurs[c] = type === "image" ? images[c] : val("o-" + c); }); }
      else if (cle === "reseaux") { section = "reseaux"; RESEAUX.forEach(([r]) => { valeurs[r] = { id: val("r-" + r + "-id"), url: val("r-" + r + "-url") }; }); }
      else if (cle === "heures") { section = "heures"; JOURS.forEach(([j]) => { valeurs[j] = val("h-" + j); }); }
      else { section = "soustraitants"; const k = cle.slice(3); valeurs[k] = {}; CH_ST.forEach(([c]) => { valeurs[k][c] = val("s-" + k + "-" + c); }); }
      const msg = $('[data-msg="' + cle + '"]', corps);
      try { await agir("affichage.modifier_organisation", { section: section, valeurs: valeurs }); if (msg) msg.textContent = "Enregistré."; toast("Enregistré."); await charger(); }
      catch (e) { if (msg) msg.textContent = e.message; toast(e.message); }
    }));
    rendre();
  }
  // « Modules et Applications » : l'ancienne vision Modules de Réglages, devenue une page. Sa colonne de gauche classe les modules par famille.
  async function pageModules(corps, fam) {
    const M = CASS.modulesUi;
    if (!M) { corps.innerHTML = '<div class="empty-state">Écran indisponible.</div>'; return; }
    await M.lire();
    const cat = M.catalogue();
    fam = fam || E.famModules || "tous";
    if (fam !== "tous" && !cat.some((m) => (m.famille || "autres") === fam)) fam = "tous";
    E.famModules = fam;
    const nbDe = (f) => (f === "tous" ? cat.length : cat.filter((m) => (m.famille || "autres") === f).length);
    E.lateral = { titre: "Modules", actif: fam, items: [{ id: "tous", libelle: "Tous les modules", n: cat.length, icone: "puzzle" }].concat(M.familles().map((f) => ({ id: f, libelle: M.famLib(f), n: nbDe(f), icone: "panorama" }))) };
    const tete = fam === "tous" ? "Tous les modules" : M.famLib(fam);
    E.pageNom = CASS.nomOnglet("menus:vue_modules"); E.fil = ["Paramètres", "Modules et Applications", tete];
    const sc = corps.closest(".sh-scene"), t = sc && sc.querySelector(".sh-titre");
    if (t) {                                                           // un titre et sa légende, comme les autres pages
      t.textContent = "Modules et Applications";
      let l = sc.querySelector(".sh-legende"); if (!l) { l = document.createElement("p"); l.className = "sh-legende"; t.after(l); }
      l.textContent = "La gestion des modules : ce qui est actif, ce qui dépend de quoi, et les réglages propres à chaque module. Un module neuf n’est jamais activé de lui-même.";
    }
    corps.innerHTML = '<div class="settings-section-title">' + esc(tete) + '</div><div class="s-hint">Activer un module branche à chaud ses menus, ses capacités et ses moteurs ; le désactiver les retire.</div>' + (fam === "tous" ? cat : cat.filter((m) => (m.famille || "autres") === fam)).map((m) => M.fiche(m, "global", fam === "tous")).join("");
    E.pageAction = (id) => pageModules(corps, id);
    const relire = async () => { await pageModules(corps, E.famModules); };
    M.gestes(corps, async () => { await relire(); CASS.disposition.rafraichir(); });
    M.lierChamps(corps, relire);
    rendre();
  }
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.menus = async function (corps, ctx) {
    const ecran = String(ctx.ecran).split(":")[1] || "";
    if (ecran === "vue_modules") await pageModules(corps);
    else if (CASS.console) { corps.innerHTML = '<div class="sh-console"></div>'; CASS.console("menus", corps.querySelector(".sh-console")); }
  };
  CASS.sceneSurMesure.affichage = async function (corps, ctx) {
    const ecran = String(ctx.ecran).split(":")[1] || "";
    if (ecran === "vue_societe") {
      await pageSociete(corps);
    } else if (ecran === "vue_info") {
      let s = {}; try { s = await agir("affichage.lire_session", {}); } catch (e) {}
      const nav = (navigator.userAgent.match(/(Firefox|Edg|Chrome|Safari)\/[\d.]+/) || ["—"])[0];
      const th = document.documentElement.getAttribute("data-habillage") || document.documentElement.getAttribute("data-theme") || "clair";
      const texteDe = (id) => { const e = document.getElementById(id); return (e && e.textContent.trim()) || "—"; };
      const sess = s.sessions || [], f = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");
      const L = [["Version actuelle", s.version || (E.d && E.d.version) || "—"], ["Dernière version stable en dépôt", "—"], ["Version d’installation initiale", "—"], 0,
        ["Session de", s.compte], ["Rôle", s.role], ["Adresse IP", s.ip || "—"], ["Navigateur et adresse", texteDe("um-ou")], ["Sites gérés", texteDe("um-sites")], ["FastPanel", texteDe("um-fp")], ["Organisation", s.organisation || "—"], ["Connecté depuis", f(sess[0] && sess[0].cree)], ["Connexion précédente", f(sess[1] && sess[1].cree)],
        ["Thème courant", th], ["Gestionnaire de menu", "Barre à groupes + colonne (affichage)"], ["Langue", navigator.language || "fr"], ["Fuseau horaire", Intl.DateTimeFormat().resolvedOptions().timeZone], ["Navigateur", nav],
        ["Présentation", document.body.classList.contains("allege") ? "Allégée" : "Complète"], ["Écran", screen.width + " × " + screen.height]];
      corps.innerHTML = '<div class="d19-page"><dl class="d19-info">' + L.map((r) => r ? "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd>" : '<dt></dt><dd><hr class="d19-sep" style="margin:6px 0"></dd>').join("") + "</dl></div>";
    } else if (CASS.console) { corps.innerHTML = '<div class="sh-console"></div>'; CASS.console("affichage", corps.querySelector(".sh-console")); }
  };

  // ── le toast, le verrouillage de bas niveau ───────────────────────────────
  let tt;
  function toast(m) { const t = $("#d19-toast"); if (!t) return; t.textContent = m; t.classList.add("v"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("v"), 2400); }
  function fermerPops() { const u = $("#usermenu"); if (u && u.classList.contains("open") && typeof window.fermerCompte === "function") window.fermerCompte(); const a = $("#alert-dropdown"); if (a && a.classList.contains("open") && typeof window.toggleAlertDropdown === "function") window.toggleAlertDropdown(); }

  // ── le dessin d'ensemble ───────────────────────────────────────────────────
  function rendre() { E.crMenu = null; rendreHaut(); rendreGauche(); rendreStrip(); if (E.panel) rendrePanel(); }
  async function charger() {
    try {
      E.d = await agir("affichage.lire_disposition", {});
      if (!E.g || !E.d.groupes.some((g) => g.id === E.g)) { E.g = E.d.groupes[0] ? E.d.groupes[0].id : ""; E.e = ""; }
      if (!E.moi) E.moi = await (await fetch("/api/moi", { headers: { "X-Session-Token": token() } })).json();
      E.compte = E.moi.compte || "";
      completerAvatar(); rendre();
    } catch (e) { console.warn("disposition :", e); }
  }
  // ── le pouls : l'état (capsule, points des groupes, pastilles) suit le Sensorium tout seul, sans rien fermer ──
  let pouleEnCours = false;
  async function pouls() {
    if (pouleEnCours || !E.d || !token() || document.hidden) return;
    pouleEnCours = true;
    try {
      const d = await agir("affichage.lire_disposition", {});
      if (d && d.etag !== E.d.etag) {
        E.d = d;
        if (!E.d.groupes.some((g) => g.id === E.g)) { E.g = E.d.groupes[0] ? E.d.groupes[0].id : ""; E.e = ""; }
        rendreHaut(); rendreGauche();                                   // ni le fil, ni les menus ouverts, ni le panneau ne sont touchés
      }
    } catch (e) { /* un raté ne casse rien : le prochain battement refait */ }
    pouleEnCours = false;
  }
  function construire() {
    if ($("#d19-top")) return;
    document.body.classList.add("d19");
    const app = $("#app-container"), corps = $(".app-body"), main = $(".app-main");
    if (!app || !corps || !main) return;
    const top = document.createElement("div"); top.id = "d19-top";
    top.innerHTML = '<button class="d19-logo" id="d19-logo" aria-label="Accueil"></button><button class="d19-ib" id="d19-burger" title="Replier / déplier le menu de gauche" aria-label="Menu">' + ico("menu") + '</button><span id="d19-nav"></span>'
      + '<button class="d19-ib" id="d19-rafr" title="Actualiser la page" aria-label="Actualiser">' + ico("refresh") + '</button><nav id="d19-groupes" aria-label="Groupes"></nav>'
      + '<div id="d19-droite"><button class="d19-ib" id="d19-btn-cass" title="Itare et Cassandra" aria-label="Itare et Cassandra">' + ico("spark") + '</button><button class="d19-ib" id="d19-search" title="Rechercher (Ctrl+K)" aria-label="Rechercher">' + ico("search") + '</button><span id="d19-bell"></span><span id="d19-theme"></span><span id="d19-vtxt"></span><span id="d19-corner"></span></div>';
    app.insertBefore(top, $(".header", app) || corps);
    // les morceaux de l'ancienne barre qui servent encore : les flèches, la cloche, le thème, l'avatar et son menu
    const deplacer = (sel, vers) => { const x = $(sel); if (x && $(vers)) $(vers).appendChild(x); };
    deplacer(".nav-fleches", "#d19-nav"); deplacer(".bell-wrap", "#d19-bell"); deplacer("#theme-btn", "#d19-theme"); deplacer("#corner", "#d19-corner");
    const side = document.createElement("aside"); side.id = "d19-side"; side.setAttribute("aria-label", "Menu du groupe");
    const scrim = document.createElement("div"); scrim.id = "d19-scrim";
    corps.insertBefore(side, main); corps.insertBefore(scrim, main);
    const cap = document.createElement("button"); cap.id = "d19-cap"; cap.type = "button"; cap.setAttribute("aria-label", "Où je suis, et l'état"); corps.appendChild(cap);
    const strip = document.createElement("div"); strip.id = "d19-strip"; main.insertBefore(strip, main.firstChild);
    const cass = document.createElement("aside"); cass.id = "d19-cass"; cass.setAttribute("aria-label", "Itare et Cassandra"); cass.innerHTML = '<div class="in"></div>'; corps.appendChild(cass);
    const autres = '<div class="d19-tip" id="d19-tip"></div><div id="d19-plus"></div><div id="d19-ms"><div class="back" data-msback="1"></div><div class="box"></div></div>'
      + '<div id="d19-pal"><div><input id="d19-pal-in" placeholder="Aller à… (groupe, entrée, page)" autocomplete="off"><div class="res"></div></div></div><div id="d19-toast" role="status"></div>';
    const bas = document.createElement("nav"); bas.id = "d19-bas"; bas.setAttribute("aria-label", "Groupes"); app.appendChild(bas);
    const reste = document.createElement("div"); reste.innerHTML = autres; while (reste.firstChild) app.appendChild(reste.firstChild);
    liens();
    new ResizeObserver(mesurer).observe(app); mesurer();
    appliquerPrefs();
  }
  function appliquerPrefs() { const app = $("#app-container"); app.classList.toggle("d19-sans-verre", !E.prefs.verre); app.classList.toggle("d19-tactile", tactile()); }
  function mesurer() {
    const app = $("#app-container"); if (!app) return;
    const w = app.getBoundingClientRect().width, k = w > 1500 ? "xl" : w > 1200 ? "l" : w > 900 ? "m" : w > 560 ? "s" : "xs";
    const avant = E.w; E.w = k; app.setAttribute("data-w", k);
    if (avant !== k) { const petit = k === "s" || k === "xs", pp = avant === "s" || avant === "xs"; if (!avant || petit !== pp) E.side = petit ? false : (E.panel && k !== "xl" ? "rail" : "full"); if (E.d) rendre(); }
    if (k !== "xs") app.classList.remove("d19-haut-masque");
    appliquerPrefs();
  }

  // ── les liens : clics, survol, clavier, gestes ─────────────────────────────
  function liens() {
    const app = $("#app-container");
    app.addEventListener("click", function (ev) {
      const c = (s) => ev.target.closest(s); let x;
      if ((x = c("#d19-logo"))) { if (typeof window.navAccueil === "function") window.navAccueil(); else if (E.d && E.d.groupes[0]) aller(E.d.groupes[0].id, ""); return; }
      if ((x = c("#d19-burger"))) { if (isXs()) { ouvrirMs(); return; } E.sideTouche = true; E.side = E.side === "rail" ? "full" : !E.side ? "full" : false; rendreGauche(); return; }
      if ((x = c("#d19-rafr"))) { const t = window.__d19Onglet || (E.actif && entree() && entree().onglet); if (t && typeof window.switchTab === "function") window.switchTab(t); toast("Page actualisée"); return; }
      if ((x = c("#d19-search"))) { palOuvrir(); return; }
      if ((x = c("#d19-btn-cass")) || (x = c("[data-cbas]"))) { $("#d19-plus").classList.remove("ouvert"); ouvrirPanel(); return; }
      if ((x = c("[data-cclose]"))) { ouvrirPanel(false); return; }
      if ((x = c("#d19-groupes .d19-gr")) || (x = c("#d19-bas [data-g]"))) {
        fermerPops();
        if (isXs() && x.dataset.bas && E.g === x.dataset.g && E.actif) { ouvrirMs(true); return; }
        aller(x.dataset.g, ""); if (isPetit() && !isXs()) { E.side = "full"; rendreGauche(); } return;
      }
      if ((x = c("[data-plus]"))) { const p = $("#d19-plus"); if (p.classList.contains("ouvert")) { p.classList.remove("ouvert"); return; } ouvrirMs(false); p.innerHTML = E.d.groupes.map((g) => '<button class="' + (g.id === E.g ? "on" : "") + '" data-pg2="' + esc(g.id) + '">' + ico(g.icone) + esc(g.libelle) + pastille(g) + "</button>").join(""); p.classList.add("ouvert"); return; }
      if ((x = c("#d19-plus [data-pg2]"))) { $("#d19-plus").classList.remove("ouvert"); aller(x.dataset.pg2, ""); return; }
      if ((x = c("[data-ms]"))) { ouvrirMs(); return; }
      if ((x = c("[data-msback]"))) { ouvrirMs(false); return; }
      if ((x = c("[data-msen]"))) { ouvrirMs(false); aller(E.g, x.dataset.msen); return; }
      if ((x = c("[data-mspin]"))) { ouvrirMs(false); aller(x.dataset.pg, x.dataset.pe, x.dataset.pv); return; }
      if ((x = c("#d19-strip [data-sx]"))) { aller(E.g, E.e, x.dataset.sx); return; }
      if ((x = c("#d19-strip [data-cr-up]"))) { remonter(); return; }
      if ((x = c("#d19-strip [data-crm]"))) { const i = +x.dataset.crm; E.crMenu = E.crMenu === i ? null : i; rendreStrip(); return; }
      if ((x = c("#d19-strip [data-crs]"))) { const ij = x.dataset.crs.split(".").map(Number), t = E.crumbs[ij[0]] && E.crumbs[ij[0]].sib[ij[1]]; E.crMenu = null; if (t && t.go) t.go(); else rendreStrip(); return; }
      if ((x = c("#d19-strip [data-cr]"))) { const k = E.crumbs[+x.dataset.cr]; E.crMenu = null; if (k && k.go) k.go(); else rendreStrip(); return; }
      if ((x = c("#d19-strip [data-pin]"))) { basculerPin(); return; }
      if (c("[data-gen-nouveau]")) { genererMdp(); return; }
      if (c("[data-gen-copier]")) { const v = document.getElementById("d19-gen-sortie").value; if (v && navigator.clipboard) navigator.clipboard.writeText(v).then(() => toast("Copié."), () => toast("Copie refusée par le navigateur.")); return; }
      if ((x = c("[data-lat]"))) { if (E.pageAction) E.pageAction(x.dataset.lat); return; }
      if (c("#d19-cap")) { capsuleAller(); return; }
      if ((x = c("#d19-side .pinned"))) { aller(x.dataset.pg, x.dataset.pe, x.dataset.pv); return; }
      if ((x = c("#d19-side [data-fm]"))) {
        const nom = x.dataset.fm;
        if (!(E.actif && E.e === "flotte")) { if (typeof window.switchTab === "function") window.switchTab("fleet"); }
        if (typeof window.fl2Ouvrir === "function") window.fl2Ouvrir(nom);
        return;
      }
      if ((x = c("#d19-side [data-fa]"))) {
        if (x.dataset.fa === "ajouter" && typeof window.openFleetAdd === "function") window.openFleetAdd();
        else if (x.dataset.fa === "relever" && typeof window.fl2Charger === "function") window.fl2Charger();
        return;
      }
      if ((x = c("#d19-side .sub"))) { if (x.dataset.e) aller(E.g, x.dataset.e, x.dataset.v); return; }
      if ((x = c("#d19-side .ent"))) {
        const id = x.dataset.e, e = ent().entrees.find((y) => y.id === id);
        if (E.side === "rail") { aller(E.g, id); return; }
        const aEnfants = e.enfants.length > 0 || id === "flotte";
        if (aEnfants && E.ouv.has(id) && E.e === id && E.actif) { E.ouv.delete(id); rendreGauche(); } else { E.ouv.add(id); aller(E.g, id); }
        return;
      }
      if (c("#d19-scrim")) { fermerSide(); return; }
      // panneau
      if ((x = c("#d19-cass [data-mode]"))) { if (!x.disabled) changerMode(x.dataset.mode); return; }
      if ((x = c("#d19-cass [data-inv]"))) { const a = x.dataset.inv; E.invites.has(a) ? E.invites.delete(a) : E.invites.add(a); rendrePanel(); return; }
      if ((x = c("#d19-cass [data-fsel]"))) { E.fmenu = !E.fmenu; E.sug = false; rendrePanel(); return; }
      if ((x = c("#d19-cass [data-fpage]"))) { const m = mode(); E.sel[m] = "page"; E.fmenu = false; const f = filCourant(m); (f ? chargerMessages(f.fil) : Promise.resolve()).then(rendrePanel); return; }
      if ((x = c("#d19-cass [data-fnew]"))) { E.sel[mode()] = "nouveau"; E.fmenu = false; rendrePanel(); return; }
      if ((x = c("#d19-cass [data-fth]"))) { const m = mode(), id = +x.dataset.fth; E.sel[m] = id; E.fmenu = false; chargerMessages(id).then(rendrePanel); return; }
      if ((x = c("#d19-cass [data-sug]"))) { E.sug = !E.sug; E.fmenu = false; if (E.sug) idees(true); rendrePanel(); return; }
      if ((x = c("#d19-cass [data-reg]"))) { E.regOuvert = !E.regOuvert; rendrePanel(); return; }
      if ((x = c("#d19-cass [data-idee-q]"))) { const i = (E.idees.idees || []).find((y) => y.id === x.dataset.ideeQ); E.sug = false; if (i) envoyer(i.titre); return; }
      if ((x = c("#d19-cass [data-idee-acte]"))) { const i = (E.idees.idees || []).find((y) => y.id === x.dataset.ideeActe); if (i) proposerActe(i); return; }
      if ((x = c("#d19-cass [data-valider]"))) { validerActe(+x.dataset.valider); return; }
      if ((x = c("#d19-cass [data-refuser]"))) { const a = E.actes[mode()][+x.dataset.refuser]; a.etat = "refuse"; E.refuses.add(a.cle); rendrePanel(); idees(true); return; }
      if ((x = c("#d19-cass [data-page]"))) { if (window.switchTab) window.switchTab(x.dataset.page); return; }
      if ((x = c("#d19-pal [data-pi]"))) { palChoisir(+x.dataset.pi); return; }
      if (c("#d19-pal > div")) return;
      if (c("#d19-pal")) { palFermer(); return; }
      if ((x = c("[data-d19-theme]"))) { if (typeof window.appliquerTheme === "function") window.appliquerTheme(x.dataset.d19Theme); setTimeout(completerAvatar, 50); return; }
      if ((x = c("[data-d19-hab]"))) { const id = x.dataset.d19Hab, r = document.documentElement; if (typeof window.appliquerTheme === "function") window.appliquerTheme(id || (r.getAttribute("data-theme") === "dark" ? "dark" : "light")); setTimeout(completerAvatar, 50); return; }
      if ((x = c("[data-d19-avid]"))) { const a = (E.d.avatar || []).find((y) => y.id === x.dataset.d19Avid); if (typeof window.fermerCompte === "function") window.fermerCompte(); if (a) { E.silence = false; marquerPage(a); ouvrirNoeud(a); } return; }
      if ((x = c("[data-d19-info]"))) { if (typeof window.fermerCompte === "function") window.fermerCompte(); marquerPage({ id: "affichage:info", ecran: "affichage:vue_info", libelle: "Info Cassandra" }); if (CASS.ouvrirEcran) CASS.ouvrirEcran("affichage:vue_info", "Info Cassandra"); return; }
      if (c("[data-d19-verre]")) { E.prefs.verre = !E.prefs.verre; sauverPrefs(); appliquerPrefs(); completerAvatar(); return; }
      if (c("[data-d19-v18]")) { try { localStorage.setItem("cass_disposition", "v18"); } catch (e) {} location.reload(); return; }
      if (E.crMenu != null && !c("#d19-strip .cr-wrap")) { E.crMenu = null; rendreStrip(); }
      if (E.sug && !c("#d19-cass .sug") && !c("[data-sug]")) { E.sug = false; rendrePanel(); }
      if (E.fmenu && !c("#d19-cass .fmenu") && !c("[data-fsel]")) { E.fmenu = false; rendrePanel(); }
      if (!c("#d19-plus") && !c("[data-plus]")) $("#d19-plus").classList.remove("ouvert");
    });
    app.addEventListener("change", function (ev) { if (/^d19-gen-(maj|min|chi|sym)$/.test(ev.target.id)) genererMdp(); });
    app.addEventListener("submit", function (ev) { if (ev.target.id === "d19-f") { ev.preventDefault(); const i = $("#d19-in"), v = i.value; i.value = ""; E.brouillon = ""; envoyer(v); } });
    app.addEventListener("input", function (ev) { if (ev.target.id === "d19-gen-long") { genererMdp(); return; } if (ev.target.id === "d19-pal-in") { palSel = 0; palRender(); } else if (ev.target.id === "d19-in") E.brouillon = ev.target.value; });
    app.addEventListener("mouseover", function (ev) {
      const it = ev.target.closest("#d19-side.rail [data-tip]"), tp = $("#d19-tip");
      if (!it) { tp.classList.remove("v"); return; }
      const r = it.getBoundingClientRect(); tp.textContent = it.dataset.tip; tp.style.left = (r.right + 8) + "px"; tp.style.top = (r.top + r.height / 2 - 14) + "px"; tp.classList.add("v");
    });
    document.addEventListener("keydown", function (ev) {
      if (!$("#d19-top") || $("#app-container").classList.contains("hidden")) return;
      const typ = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); palOuvrir(); return; }
      if (ev.key === "Escape" && E.crMenu != null) { E.crMenu = null; rendreStrip(); return; }
      if (ev.altKey && ev.key === "ArrowUp") { ev.preventDefault(); remonter(); return; }
      if (ev.key === "Escape") { if (E.fmenu) { E.fmenu = false; rendrePanel(); return; } if (E.sug) { E.sug = false; rendrePanel(); return; } palFermer(); if (E.panel) ouvrirPanel(false); return; }
      if ($("#d19-pal").classList.contains("ouvert")) { if (ev.key === "ArrowDown") { ev.preventDefault(); palSel = Math.min(palSel + 1, palRes.length - 1); palRender(); } else if (ev.key === "ArrowUp") { ev.preventDefault(); palSel = Math.max(palSel - 1, 0); palRender(); } else if (ev.key === "Enter") { ev.preventDefault(); palChoisir(palSel); } return; }
      if (ev.altKey && /^[1-9]$/.test(ev.key) && E.d && E.d.groupes[+ev.key - 1]) { ev.preventDefault(); aller(E.d.groupes[+ev.key - 1].id, ""); return; }
      if (ev.key === "[" && !typ) { E.sideTouche = true; E.side = E.side === "rail" ? "full" : !E.side ? "full" : false; rendreGauche(); }
    });
    // le haut se masque en descendant (téléphone)
    let ly = 0;
    $(".app-main").addEventListener("scroll", function (ev) { if (!isXs()) return; const y = ev.target.scrollTop || 0, d = y - ly; if (y > 90 && d > 10) app.classList.add("d19-haut-masque"); else if (d < -10 || y < 20) app.classList.remove("d19-haut-masque"); ly = y; }, true);
    // les gestes (tablette : bord gauche ; téléphone : poignée du panneau, tirer pour actualiser)
    let tx = 0, ty = 0, tm = "";
    document.addEventListener("touchstart", function (ev) {
      if (!$("#d19-top")) return; const t = ev.touches[0], a = app.getBoundingClientRect(); tx = t.clientX; ty = t.clientY; tm = "";
      if (ev.target.closest("[data-poignee]")) tm = "feuille";
      else if (E.w === "s" && !E.side && tx - a.left < 24) tm = "bord";
      else if (E.w === "s" && E.side && ev.target.closest("#d19-side")) tm = "fermer";
    }, { passive: true });
    document.addEventListener("touchend", function (ev) {
      if (!tm) return; const t = ev.changedTouches[0], dx = t.clientX - tx, dy = t.clientY - ty;
      if (tm === "bord" && dx > 60 && Math.abs(dy) < 50) { E.side = "full"; rendreGauche(); }
      else if (tm === "fermer" && dx < -60 && Math.abs(dy) < 50) fermerSide();
      else if (tm === "feuille" && dy > 60) ouvrirPanel(false);
      tm = "";
    }, { passive: true });
  }

  // ── le départ ──────────────────────────────────────────────────────────────
  let lance = false;
  async function lancer() {
    if (!token()) return;
    construire();
    const avant = E.compte;
    await charger();
    if (avant && avant !== E.compte) { E.msgs = {}; E.fils = { itare: [], cassandra: [], inv: [] }; E.actes = { itare: [], cassandra: [], inv: [] }; E.faits.clear(); E.refuses.clear(); }
    if (!E.actif && E.d && E.d.groupes[0]) {
      const cur = (document.querySelector(".tab-content.active") || {}).id || "";
      suivre(cur.replace(/^tab-/, ""));
      if (!E.actif) { E.g = E.d.groupes[0].id; E.e = ""; rendre(); }
    }
    idees(true);
    if (!lance) {
      lance = true;
      setInterval(pouls, 15000); document.addEventListener("visibilitychange", pouls);
      setInterval(function () { if (token() && !document.hidden && E.d) idees(); }, 60000);
      const sw = window.switchTab;
      const bs = window.buSeg;
      if (typeof bs === "function") window.buSeg = function (v) { const r = bs.apply(this, arguments); try { suivreSegment(v); } catch (e) {} return r; };
      window.switchTab = function (name) { const r = sw.apply(this, arguments); window.__d19Onglet = name; try { suivre(name); } catch (e) {} return r; };
      if (typeof window.vuRendre === "function") {
        const vr = window.vuRendre;
        window.vuRendre = function () { const r = vr.apply(this, arguments); try { recopierEtatPanorama(); } catch (e) {} return r; };
      }
      if (typeof window.flRail === "function") {
        const fr = window.flRail;
        window.flRail = function () { const r = fr.apply(this, arguments); try { if (E.e === "flotte") rendreGauche(); } catch (e) {} return r; };
      }
    }
  }
  CASS.disposition = { rafraichir: charger, aller: aller, ouvrirPanel: ouvrirPanel };
  const surConnexion = CASS.surConnexion;
  CASS.surConnexion = function () { if (surConnexion) surConnexion.apply(this, arguments); lancer(); };
  if (token()) setTimeout(lancer, 400);
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
