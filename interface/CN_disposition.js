// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La disposition V19 : barre du haut (groupes), colonne de gauche, menu de l'avatar conservé
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #9dc14a
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La disposition V19 : barre du haut (groupes), colonne de gauche, menu de l'avatar conservé, panneau conversationnel (Itare, Cassandra, invités).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=9dc14a ▼▼▼
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
    down: '<path d="M6 9l6 6 6-6"/>', right: '<path d="M9 6l6 6-6 6"/>', left: '<path d="M15 6l-6 6 6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>', dots: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5"/>',
  };
  const ico = (k, c) => '<svg class="d-i' + (c ? " " + c : "") + '" viewBox="0 0 24 24">' + (IC[k] || IC.plus) + "</svg>";

  // ── l'état ─────────────────────────────────────────────────────────────────
  const E = {
    d: null, moi: null, compte: "", g: "", e: "", vue: "", actif: null, side: "full", sideAvant: "full", sideTouche: false, ouv: new Set(),
    panel: false, manual: null, sel: { itare: "page", cassandra: "page", inv: "page" }, fils: { itare: [], cassandra: [], inv: [] }, msgs: {}, dernier: {},
    invites: new Set(["itare"]), fmenu: false, sug: false, regOuvert: false, idees: { mode: "itare", idees: [], urgent: false, actes: {} }, actes: { itare: [], cassandra: [], inv: [] },
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
  const VUES_BUREAU = { jour: "today", suivre: "proj", courrier: "mail", repertoire: "rep" };
  function pontVue(entreeId, vue) {
    if (entreeId !== "accueil" || !vue) return;
    setTimeout(function () {
      if (vue === "documents" && typeof window.buAllerDocuments === "function") window.buAllerDocuments();
      else if (VUES_BUREAU[vue] && typeof window.buSeg === "function") window.buSeg(VUES_BUREAU[vue]);
    }, 80);
  }
  function ouvrirNoeud(n, vue) {
    if (n.onglet) { window.switchTab(n.onglet); pontVue(n.id.split(".")[0], vue || n.vue); }
    else if (n.ecran === "menus:vue_modules") { window.switchTab("settings"); setTimeout(function () { if (typeof window.setVision === "function") window.setVision("modules"); }, 250); }
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
    let trouve = null;
    for (const g of E.d.groupes) for (const e of g.entrees) {
      if (e.onglet === nom) trouve = { g: g.id, e: e.id, vue: E.actif && E.actif.e === e.id ? E.actif.vue : "" };
      else if (e.ecran && CASS.nomOnglet && CASS.nomOnglet(e.ecran) === nom) trouve = { g: g.id, e: e.id, vue: "" };
      else for (const f of e.enfants) if (f.ecran && CASS.nomOnglet && CASS.nomOnglet(f.ecran) === nom) trouve = { g: g.id, e: e.id, vue: f.vue || f.id };
    }
    if (trouve) { E.g = trouve.g; E.e = trouve.e; E.vue = trouve.vue; E.actif = trouve; E.hors = ""; }
    else { E.actif = null; E.hors = nom; }
    rendre();
  }

  // ── le rendu : haut ────────────────────────────────────────────────────────
  const pastille = (g) => (g.niveau === "danger" || g.niveau === "alerte" ? '<span class="d19-dot ' + g.niveau + '"></span>' : "");
  function rendreHaut() {
    if (!E.d) return;
    const lg = $("#d19-logo"), o = E.d.organisation || {};
    lg.className = "d19-logo" + (o.logo ? " img" : "") + (E.d.niveau === "danger" ? " s-danger" : E.d.niveau === "alerte" ? " s-alerte" : "");
    lg.title = (o.nom || "Cassandra") + " · " + (E.d.niveau === "danger" ? "un point urgent à regarder" : E.d.niveau === "alerte" ? "des points à regarder" : "tout est en ordre");
    lg.style.backgroundImage = o.logo ? "url(" + o.logo + ")" : "";
    lg.textContent = o.logo ? "" : (o.nom || "C").trim().charAt(0).toUpperCase();
    $("#d19-groupes").innerHTML = E.d.groupes.map((g, i) => '<button class="d19-gr' + (g.id === E.g && E.actif ? " on" : "") + '" data-g="' + esc(g.id) + '" data-tip="' + esc(g.libelle) + " · Alt+" + (i + 1) + '" aria-label="' + esc(g.libelle) + '">' + ico(g.icone) + pastille(g) + "</button>").join("");
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
  function rendreGauche() {
    const g = ent(), sd = $("#d19-side"); if (!g) { sd.innerHTML = ""; return; }
    const rail = E.side === "rail" && !isPetit();
    sd.classList.toggle("ferme", !E.side);
    sd.classList.toggle("rail", rail);
    $("#d19-scrim").classList.toggle("on", !!E.side && E.side !== "rail" && isPetit());
    let h = "";
    const ep = epinglesVisibles();
    if (ep.length) h += "<h2>Épinglés</h2>" + ep.map((p) => '<button class="d19-si pinned" data-tip="' + esc(p.libelle) + '" data-pg="' + esc(p.groupe) + '" data-pe="' + esc(p.entree) + '" data-pv="' + esc(p.vue || "") + '">' + ico("star") + "<span>" + esc(p.libelle) + "</span></button>").join("") + '<hr class="d19-sep">';
    h += "<h2>" + esc(g.libelle) + "</h2>";
    const chev = (o) => ico("right", "car" + (o ? " ouv" : ""));
    for (const e of g.entrees) {
      const ouv = E.ouv.has(e.id) && e.enfants.length, actif = E.actif && E.e === e.id && E.g === g.id;
      h += '<button class="d19-si ent' + (actif && (!ouv || rail) ? " on" : "") + '" data-tip="' + esc(e.libelle) + '" data-e="' + esc(e.id) + '">' + ico(e.icone) + "<span>" + esc(e.libelle) + "</span>" + (!ouv ? nbDe(e) : "") + (e.enfants.length ? chev(ouv) : "") + "</button>";
      if (ouv) h += e.enfants.map((f) => '<button class="d19-si sub' + (actif && E.vue === (f.vue || f.id) ? " on" : "") + '" data-e="' + esc(e.id) + '" data-v="' + esc(f.vue || f.id) + '"><span class="pt"></span>' + esc(f.libelle) + nbDe(f) + "</button>").join("");
    }
    sd.innerHTML = h;
  }
  function fermerSide() { E.side = false; rendreGauche(); }

  // ── le rendu : bandeau de page / pastilles ────────────────────────────────
  const estPin = () => !!(E.d && (E.d.epingles || []).some((p) => p.cle === cleDe(E.g, E.e, E.vue)));
  function rendreStrip() {
    const el = $("#d19-strip"), g = ent(), e = entree();
    if (!E.d || !g || !e || !E.actif) { el.innerHTML = ""; el.style.display = "none"; return; }
    el.style.display = "";
    const parts = [g.libelle, e.libelle].concat(E.vue ? [((e.enfants.find((f) => (f.vue || f.id) === E.vue) || {}).libelle) || E.vue] : []);
    el.innerHTML = '<div class="fil">' + parts.map((p, i) => (i < parts.length - 1 ? '<button data-fil="' + i + '">' + esc(p) + "</button><span>›</span>" : "<span>" + esc(p) + "</span>")).join("") + "</div>"
      + '<button class="pin' + (estPin() ? " on" : "") + '" data-pin="1" title="Épingler cette page" aria-label="Épingler cette page">' + ico("star") + "</button>"
      + '<button class="tit" data-ms="1" aria-label="Changer d’entrée">' + ico(e.icone) + "<span>" + esc(e.libelle) + "</span>" + ico("down") + "</button>"
      + '<div class="pills" id="d19-pills">' + e.enfants.map((f) => '<button class="pl' + (E.vue === (f.vue || f.id) ? " on" : "") + '" data-sx="' + esc(f.vue || f.id) + '">' + esc(f.libelle) + "</button>").join("") + "</div>";
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

  // ── l'aperçu au survol d'une dalle ─────────────────────────────────────────
  let flyT = null;
  function flyOuvrir(btn) {
    const g = E.d.groupes.find((x) => x.id === btn.dataset.g); if (!g) return;
    const f = $("#d19-fly");
    f.innerHTML = "<h3>" + esc(g.libelle) + '</h3><div class="col">' + g.entrees.map((e) => '<div class="en"><b>' + ico(e.icone) + esc(e.libelle) + "</b>"
      + (e.enfants.length ? e.enfants.slice(0, 6).map((x) => '<button data-fg="' + esc(g.id) + '" data-fe="' + esc(e.id) + '" data-fv="' + esc(x.vue || x.id) + '">' + esc(x.libelle) + nbDe(x) + "</button>").join("") + (e.enfants.length > 6 ? '<button class="plus" data-fg="' + esc(g.id) + '" data-fe="' + esc(e.id) + '" data-fv="">Tout voir (' + e.enfants.length + ")</button>" : "")
        : '<button data-fg="' + esc(g.id) + '" data-fe="' + esc(e.id) + '" data-fv="">Ouvrir' + nbDe(e) + "</button>") + "</div>").join("") + "</div>";
    f.classList.add("ouvert");
    const a = $("#app-container").getBoundingClientRect(), r = btn.getBoundingClientRect();
    f.style.left = Math.max(8, Math.min(r.left - a.left - 6, a.width - f.offsetWidth - 8)) + "px";
  }
  const flyFermer = () => $("#d19-fly").classList.remove("ouvert");
  const peutSurvoler = () => !isPetit() && !tactile() && window.matchMedia && matchMedia("(hover:hover)").matches;

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
      ouvrirMs(false); flyFermer(); rendrePanel();
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
    else if (x.av) { const a = (E.d.avatar || []).find((y) => y.id === x.av); if (a) ouvrirNoeud(a); }
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
  function completerAvatar() {
    const um = $("#usermenu"); if (!um) return;
    $$("[data-d19-av]", um).forEach((x) => x.remove());
    const hote = $(".um-acts", um); if (!hote) return;
    const sec = document.createElement("div"); sec.className = "um-sec"; sec.setAttribute("data-d19-av", "1");
    sec.innerHTML = '<div class="um-h">Organisation et paramètres</div><div class="um-acts">' + (E.d.avatar || []).map((a) => '<button class="um-i" role="menuitem" data-d19-avid="' + esc(a.id) + '">' + ico(a.icone || "info") + esc(a.libelle) + "</button>").join("")
      + '<button class="um-i" role="menuitem" data-d19-verre="1">' + ico("palette") + "Verre dépoli : " + (E.prefs.verre ? "oui" : "non") + "</button>"
      + '<button class="um-i" role="menuitem" data-d19-v18="1">' + ico("menu") + "Revenir à l’ancienne disposition</button></div>";
    hote.parentNode.insertBefore(sec, hote);
  }

  // ── les pages propres : Société / Organisation, Info Cassandra ─────────────
  function redimensionner(fichier, fin) {
    const r = new FileReader();
    r.onload = function () {
      const img = new Image();
      img.onload = function () {
        const t = Math.min(1, 256 / Math.max(img.width, img.height)), c = document.createElement("canvas");
        c.width = Math.max(1, Math.round(img.width * t)); c.height = Math.max(1, Math.round(img.height * t));
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        let u = c.toDataURL("image/png"); if (u.length > 170000) u = c.toDataURL("image/jpeg", 0.85);
        fin(u.length <= 175000 ? u : "");
      };
      img.onerror = () => fin("");
      img.src = r.result;
    };
    r.readAsDataURL(fichier);
  }
  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.affichage = async function (corps, ctx) {
    const ecran = String(ctx.ecran).split(":")[1] || "";
    if (ecran === "vue_societe") {
      const o = await agir("affichage.lire_organisation", {});
      let logo = o.logo || "";
      corps.innerHTML = '<div class="d19-page"><h1>Société / Organisation</h1><p class="sous">Ce que Cassandra affiche pour ton organisation : son nom et son logo, en haut à gauche de chaque écran. Par défaut, ceux de Cassandra.</p><div class="d19-carte"><div class="d19-form">'
        + '<label for="o-nom">Nom</label><input type="text" id="o-nom" value="' + esc(o.nom) + '" autocomplete="off">'
        + '<label>Logo</label><div class="d19-logozone"><span class="d19-apercu" id="o-ap"></span><label class="d19-btn sec" for="o-logo" style="cursor:pointer">Choisir une image…</label><input type="file" id="o-logo" accept="image/png,image/jpeg,image/webp,image/gif" hidden><button type="button" class="d19-btn sec" id="o-rst">Logo de Cassandra</button></div>'
        + '<label for="o-forme">Forme juridique</label><input type="text" id="o-forme" value="' + esc(o.forme) + '" autocomplete="off">'
        + '<label for="o-id">Identifiant légal</label><input type="text" id="o-id" value="' + esc(o.identifiant) + '" autocomplete="off">'
        + '<label for="o-adr">Adresse</label><input type="text" id="o-adr" value="' + esc(o.adresse) + '" autocomplete="off">'
        + '<label for="o-tz">Fuseau horaire</label><input type="text" id="o-tz" value="' + esc(o.fuseau) + '" autocomplete="off">'
        + '<label for="o-lg">Langue par défaut</label><select id="o-lg"><option value="fr"' + (o.langue === "fr" ? " selected" : "") + '>Français</option><option value="en"' + (o.langue === "en" ? " selected" : "") + '>English</option></select>'
        + '</div><p style="margin:16px 0 0"><button class="d19-btn" id="o-ok">Enregistrer</button> <span id="o-msg" style="margin-left:10px;color:var(--txt-faint)"></span></p></div></div>';
      const ap = $("#o-ap", corps), maj = () => { ap.style.backgroundImage = logo ? "url(" + logo + ")" : ""; ap.textContent = logo ? "" : ($("#o-nom", corps).value || "C").trim().charAt(0).toUpperCase(); };
      maj();
      $("#o-nom", corps).addEventListener("input", maj);
      $("#o-logo", corps).addEventListener("change", function (ev) { const f = ev.target.files && ev.target.files[0]; if (f) redimensionner(f, function (u) { if (!u) { $("#o-msg", corps).textContent = "Image trop lourde ou illisible."; return; } logo = u; maj(); }); });
      $("#o-rst", corps).addEventListener("click", function () { logo = ""; maj(); });
      $("#o-ok", corps).addEventListener("click", async function () {
        try { await agir("affichage.modifier_organisation", { nom: $("#o-nom", corps).value, forme: $("#o-forme", corps).value, identifiant: $("#o-id", corps).value, adresse: $("#o-adr", corps).value, fuseau: $("#o-tz", corps).value, langue: $("#o-lg", corps).value, logo: logo });
          $("#o-msg", corps).textContent = "Enregistré."; await charger(); } catch (e) { $("#o-msg", corps).textContent = e.message; }
      });
    } else if (ecran === "vue_info") {
      let s = {}; try { s = await agir("affichage.lire_session", {}); } catch (e) {}
      const nav = (navigator.userAgent.match(/(Firefox|Edg|Chrome|Safari)\/[\d.]+/) || ["—"])[0];
      const th = document.documentElement.getAttribute("data-habillage") || document.documentElement.getAttribute("data-theme") || "clair";
      const sess = s.sessions || [], f = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");
      const L = [["Version actuelle", s.version || (E.d && E.d.version) || "—"], ["Dernière version stable en dépôt", "—"], ["Version d’installation initiale", "—"], 0,
        ["Session de", s.compte], ["Rôle", s.role], ["Adresse IP", s.ip || "—"], ["Organisation", s.organisation || "—"], ["Connecté depuis", f(sess[0] && sess[0].cree)], ["Connexion précédente", f(sess[1] && sess[1].cree)],
        ["Thème courant", th], ["Gestionnaire de menu", "Barre à groupes + colonne (affichage)"], ["Langue", s.langue || "fr"], ["Fuseau horaire", Intl.DateTimeFormat().resolvedOptions().timeZone], ["Navigateur", nav],
        ["Présentation", document.body.classList.contains("allege") ? "Allégée" : "Complète"], ["Écran", screen.width + " × " + screen.height]];
      corps.innerHTML = '<div class="d19-page"><h1>Info Cassandra</h1><p class="sous">Version du logiciel, puis détail de la session en cours.</p><dl class="d19-info">' + L.map((r) => r ? "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd>" : '<dt></dt><dd><hr class="d19-sep" style="margin:6px 0"></dd>').join("") + "</dl></div>";
    } else if (CASS.console) { corps.innerHTML = '<div class="sh-console"></div>'; CASS.console("affichage", corps.querySelector(".sh-console")); }
  };

  // ── le toast, le verrouillage de bas niveau ───────────────────────────────
  let tt;
  function toast(m) { const t = $("#d19-toast"); if (!t) return; t.textContent = m; t.classList.add("v"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("v"), 2400); }
  function fermerPops() { const u = $("#usermenu"); if (u && u.classList.contains("open") && typeof window.fermerCompte === "function") window.fermerCompte(); const a = $("#alert-dropdown"); if (a && a.classList.contains("open") && typeof window.toggleAlertDropdown === "function") window.toggleAlertDropdown(); }

  // ── le dessin d'ensemble ───────────────────────────────────────────────────
  function rendre() { rendreHaut(); rendreGauche(); rendreStrip(); if (E.panel) rendrePanel(); }
  async function charger() {
    try {
      E.d = await agir("affichage.lire_disposition", {});
      if (!E.g || !E.d.groupes.some((g) => g.id === E.g)) { E.g = E.d.groupes[0] ? E.d.groupes[0].id : ""; E.e = ""; }
      if (!E.moi) E.moi = await (await fetch("/api/moi", { headers: { "X-Session-Token": token() } })).json();
      E.compte = E.moi.compte || "";
      completerAvatar(); rendre();
    } catch (e) { console.warn("disposition :", e); }
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
    const strip = document.createElement("div"); strip.id = "d19-strip"; main.insertBefore(strip, main.firstChild);
    const cass = document.createElement("aside"); cass.id = "d19-cass"; cass.setAttribute("aria-label", "Itare et Cassandra"); cass.innerHTML = '<div class="in"></div>'; corps.appendChild(cass);
    const autres = '<div id="d19-fly"></div><div class="d19-tip" id="d19-tip"></div><div id="d19-plus"></div><div id="d19-ms"><div class="back" data-msback="1"></div><div class="box"></div></div>'
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
    if (k === "s" || k === "xs") flyFermer();
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
        flyFermer(); fermerPops();
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
      if ((x = c("#d19-strip [data-fil]"))) { if (+x.dataset.fil === 0) aller(E.g, ""); return; }
      if ((x = c("#d19-strip [data-pin]"))) { basculerPin(); return; }
      if ((x = c("#d19-side .pinned"))) { aller(x.dataset.pg, x.dataset.pe, x.dataset.pv); return; }
      if ((x = c("#d19-side .sub"))) { aller(E.g, x.dataset.e, x.dataset.v); return; }
      if ((x = c("#d19-side .ent"))) {
        const id = x.dataset.e, e = ent().entrees.find((y) => y.id === id);
        if (E.side === "rail") { aller(E.g, id); return; }
        if (e.enfants.length && E.ouv.has(id) && E.e === id && E.actif) { E.ouv.delete(id); rendreGauche(); } else { E.ouv.add(id); aller(E.g, id); }
        return;
      }
      if ((x = c("#d19-fly [data-fg]"))) { flyFermer(); aller(x.dataset.fg, x.dataset.fe, x.dataset.fv); return; }
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
      if ((x = c("[data-d19-avid]"))) { const a = (E.d.avatar || []).find((y) => y.id === x.dataset.d19Avid); if (typeof window.fermerCompte === "function") window.fermerCompte(); if (a) { E.silence = false; ouvrirNoeud(a); } return; }
      if (c("[data-d19-verre]")) { E.prefs.verre = !E.prefs.verre; sauverPrefs(); appliquerPrefs(); completerAvatar(); return; }
      if (c("[data-d19-v18]")) { try { localStorage.setItem("cass_disposition", "v18"); } catch (e) {} location.reload(); return; }
      if (E.sug && !c("#d19-cass .sug") && !c("[data-sug]")) { E.sug = false; rendrePanel(); }
      if (E.fmenu && !c("#d19-cass .fmenu") && !c("[data-fsel]")) { E.fmenu = false; rendrePanel(); }
      if (!c("#d19-plus") && !c("[data-plus]")) $("#d19-plus").classList.remove("ouvert");
    });
    app.addEventListener("submit", function (ev) { if (ev.target.id === "d19-f") { ev.preventDefault(); const i = $("#d19-in"), v = i.value; i.value = ""; E.brouillon = ""; envoyer(v); } });
    app.addEventListener("input", function (ev) { if (ev.target.id === "d19-pal-in") { palSel = 0; palRender(); } else if (ev.target.id === "d19-in") E.brouillon = ev.target.value; });
    app.addEventListener("mouseover", function (ev) {
      const b = ev.target.closest("#d19-groupes .d19-gr");
      if (b && peutSurvoler()) { clearTimeout(flyT); flyT = setTimeout(() => flyOuvrir(b), $("#d19-fly").classList.contains("ouvert") ? 60 : 280); return; }
      if (ev.target.closest("#d19-fly")) clearTimeout(flyT);
      const it = ev.target.closest("#d19-side.rail [data-tip]"), tp = $("#d19-tip");
      if (!it) { tp.classList.remove("v"); return; }
      const r = it.getBoundingClientRect(); tp.textContent = it.dataset.tip; tp.style.left = (r.right + 8) + "px"; tp.style.top = (r.top + r.height / 2 - 14) + "px"; tp.classList.add("v");
    });
    app.addEventListener("mouseout", function (ev) { if (ev.target.closest("#d19-groupes .d19-gr") || ev.target.closest("#d19-fly")) { clearTimeout(flyT); flyT = setTimeout(flyFermer, 240); } });
    document.addEventListener("keydown", function (ev) {
      if (!$("#d19-top") || $("#app-container").classList.contains("hidden")) return;
      const typ = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); palOuvrir(); return; }
      if (ev.key === "Escape") { if (E.fmenu) { E.fmenu = false; rendrePanel(); return; } if (E.sug) { E.sug = false; rendrePanel(); return; } palFermer(); flyFermer(); if (E.panel) ouvrirPanel(false); return; }
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
      setInterval(function () { if (token() && !document.hidden && E.d) { charger().then(() => idees()); } }, 60000);
      const sw = window.switchTab;
      window.switchTab = function (name) { const r = sw.apply(this, arguments); window.__d19Onglet = name; try { suivre(name); } catch (e) {} return r; };
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
