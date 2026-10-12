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
  CASS.agir = async function (cap, args) {
    const r = await fetch("/api/agir/" + cap, { method: "POST", headers: { "X-Session-Token": token() }, body: JSON.stringify({ args: args || {} }) });
    let d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || (d.statut !== "faite" && d.statut !== "racontee" && d.statut !== "simulee")) throw new Error(d.erreur || d.raison || d.statut || ("HTTP " + r.status));
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
  CASS.dependances = { memory: ["memoire"], sensorium: ["sensorium"], overview: ["sensorium"], mysites: ["sites"], fastpanel: ["fastpanel"] };
  // Les modules qu'un écran V18 couvre déjà : leur entrée de menu ne s'ajoute pas une seconde fois.
  CASS.couvre = { memoire: "memory", sensorium: "sensorium", sites: "mysites", fastpanel: "fastpanel", courrier: "bureau", notes: "bureau", taches: "bureau", agenda: "bureau", contacts: "bureau", projets: "bureau", comptes: "settings", modeles: "settings", agents: "salon", notifications: "bureau" };
  function actifs(modules) { return new Set((modules || []).filter((m) => m.etat === "actif" || m.actif).map((m) => m.id)); }

  function rail(modules, arbre) {
    const ok = actifs(modules);
    document.querySelectorAll(".sb-item[data-tab]").forEach((it) => {
      const dep = CASS.dependances[it.getAttribute("data-tab")];
      if (dep && !dep.every((m) => ok.has(m))) { it.style.display = "none"; it.setAttribute("data-absent", "1"); } else if (it.getAttribute("data-absent")) { it.style.display = ""; it.removeAttribute("data-absent"); }
    });
    // le groupe des modules : les entrées de menu dont le module n'a pas d'écran V18
    const feuilles = [];
    (function marcher(ns) { for (const n of ns || []) { if (n.ecran) feuilles.push(n); marcher(n.enfants); } })(arbre);
    const propres = feuilles.filter((f) => !CASS.couvre[f.module]);
    let g = document.getElementById("sb-modules");
    if (g) g.remove();
    if (!propres.length) return;
    g = document.createElement("div");
    g.className = "sb-group open"; g.id = "sb-modules"; g.setAttribute("data-grp", "modules");
    g.innerHTML = '<div class="sb-head" onclick="sbToggle(this)">Modules <span class="sb-caret">▸</span></div><div class="sb-sub">' +
      propres.map((f) => '<div class="sb-item" data-tab="' + esc(nomOnglet(f.ecran)) + '" onclick="switchTab(\'' + esc(nomOnglet(f.ecran)) + '\')"><span class="sb-dot"></span>' + esc(f.libelle) + "</div>").join("") + "</div>";
    document.getElementById("sidebar").appendChild(g);
    for (const f of propres) preparerScene(f.ecran, f.libelle);
  }
  const nomOnglet = (ecran) => "mod-" + String(ecran).replace(/[^a-z0-9]+/gi, "-");

  // ── 3. la scène générique ──────────────────────────────────────────────────
  function preparerScene(ecran, titre) {
    const nom = nomOnglet(ecran);
    if (document.getElementById("tab-" + nom)) return;
    const d = document.createElement("div");
    d.id = "tab-" + nom; d.className = "tab-content"; d.setAttribute("data-scene", ecran);
    d.innerHTML = '<div class="sh-scene"><h2 class="sh-titre">' + esc(titre) + '</h2><div class="sh-corps"><div class="empty-state">Chargement…</div></div></div>';
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
      const e = await CASS.agir("affichage.lire_ecran", { ecran: racine.getAttribute("data-scene"), role: moi.admin ? "admin" : "utilisateur", compte: moi.compte });
      const zones = e.zones || {};
      const html = ["entete", "principal", "lateral"].map((z) => (zones[z] || []).map(tuile).join("")).join("");
      corps.innerHTML = html ? '<div class="sh-grille">' + html + "</div>" : '<div class="empty-state">Ce module n’a pas encore déclaré de tuile pour cet écran.</div>';
    } catch (err) { corps.innerHTML = '<div class="empty-state">' + esc(err.message) + "</div>"; }
  }
  const switchTabOrigine = window.switchTab;
  window.switchTab = function (name, sansHistorique) {
    const r = switchTabOrigine.apply(this, arguments);
    if (typeof name === "string" && name.indexOf("mod-") === 0) dessinerScene(name);
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
