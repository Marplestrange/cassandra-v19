// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Sites : l'écran du module
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #64f129
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine les pages du module sites (vue d'ensemble, tous les sites, la page d'un site, alertes, disponibilité, demandes, journal) ; ses pages sont les sous-entrées de « Sites » dans le menu de gauche
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.sites) qui remplace l'onglet V18 « mysites » ; tout vient des capacités sites.* ; l'état vit hors de la scène, car le shell la redessine à chaque ouverture ; window.stVue reçoit la page demandée par le menu, window.stOpen ouvre un site depuis un autre écran
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=64f129 ▼▼▼
// Sites : l'écran du module. Il remplace l'onglet V18 « mysites » ; ses pages sont les sous-menus de « Sites » dans le menu de gauche
// (le rail interne de l'ancien écran a disparu). Lot 1 : ce que les capacités sites.* savent déjà rendre, sans rien inventer.
(function () {
  "use strict";
  const CASS = window.CASS;
  const K = CASS.kit;
  const esc = K.esc, agir = K.agir, dire = K.dire;
  const PAGES = { vue: "Vue d’ensemble", sites: "Tous les sites", alertes: "Alertes", dispo: "Disponibilité", demandes: "Demandes", journal: "Journal" };
  const SOUS = {
    vue: "L’état de tes sites, ce qui demande un geste, et d’où viennent les chiffres.",
    sites: "Le pire d’abord. Un clic ouvre la page d’un site.",
    alertes: "Ce qui demande un geste, puis les coupures et les retours.",
    dispo: "La part du temps où chaque site a répondu, sur la période choisie.",
    demandes: "Les demandes d’adossement au panneau, et les accords donnés par les propriétaires.",
    journal: "Les gestes faits sur les sites et ce que la veille a vu, fondus.",
  };
  const ONGLETS = [["apercu", "Aperçu"], ["dispo", "Disponibilité"], ["heberg", "Hébergement"], ["liens", "Liens"], ["journal", "Journal"]];
  const VERBES = { declare: "déclaré", declare_annule: "déclaration annulée", retire: "retiré", attribue: "attribué", transfere: "transféré", demande: "adossement demandé", adossement_fait: "adossé", adossement_refuse: "adossement refusé",
    accord: "accord donné", lien: "rattaché", delie: "lien retiré", panne: "coupure", retour: "de retour", decouverte: "découvert" };
  const FAMILLES = [["", "tout"], ["coupures", "coupures"], ["gestes", "gestes"], ["demandes", "demandes et accords"]];
  const FAM_DE = (v) => (["panne", "retour", "decouverte"].includes(v) ? "coupures" : ["demande", "adossement_fait", "adossement_refuse", "accord"].includes(v) ? "demandes" : "gestes");
  const GENRES = [["project", "projet"], ["contact", "contact"], ["machine", "machine"], ["note", "note"]];
  const PAR = 25;
  const CSS = ".si .fil{font-size:12.5px;color:var(--txt-faint)}.si .fil a{cursor:pointer;color:var(--accent)}" +
    ".si .verdict{display:flex;gap:14px;align-items:stretch}.si .vm{flex:none;width:5px;border-radius:4px;background:var(--ok)}.si .vm.al{background:var(--warn)}.si .vm.dg{background:var(--danger)}.si .vt{font:700 19px/1.3 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".si .rows{display:flex;flex-direction:column;gap:6px}.si .row{display:grid;grid-template-columns:auto minmax(0,1.6fr) minmax(0,1fr) auto;gap:12px;align-items:center;border:1px solid var(--line);border-radius:13px;padding:10px 13px;background:var(--surface);text-align:left;color:var(--txt);font:inherit;width:100%}" +
    ".si button.row{cursor:pointer}.si button.row:hover{border-color:var(--accent)}.si .row.c2{grid-template-columns:auto minmax(0,1fr) auto}.si .row.c1{grid-template-columns:minmax(0,1fr) auto}" +
    ".si .nm{min-width:0}.si .nm b{display:block;color:var(--txt-strong,var(--txt));overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.si .nm small{display:block;color:var(--txt-faint);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".si .pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:4px}.si .cote{display:flex;flex-direction:column;align-items:flex-end;gap:2px;font:500 12.5px ui-monospace,'JetBrains Mono',Menlo,monospace;color:var(--txt-soft);white-space:nowrap}" +
    ".si .vg{flex:none;width:46px;height:46px;border-radius:11px;display:grid;place-items:center;font:650 14px ui-monospace,Menlo,monospace;background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent)}.si .vg.dg{background:color-mix(in srgb,var(--danger) 13%,transparent);color:var(--danger)}.si .vg.gd{width:64px;height:64px;font-size:19px;border-radius:15px}" +
    ".si .bande{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:2px;height:26px;min-width:0}.si .bande i{border-radius:2px;background:var(--ok);opacity:.85}.si .bande i.w{background:var(--warn)}.si .bande i.d{background:var(--danger)}.si .bande i.n{background:var(--line-strong,var(--line))}" +
    ".si .leg{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--txt-faint)}.si .leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}" +
    ".si dl.g{display:grid;grid-template-columns:150px minmax(0,1fr);gap:7px 14px;font-size:13.5px;margin:0}.si dl.g dt{color:var(--txt-faint)}.si dl.g dd{margin:0;color:var(--txt-strong,var(--txt));overflow-wrap:anywhere}" +
    ".si .jl{display:grid;gap:7px;font-size:13px}.si .jl>div{display:grid;grid-template-columns:92px auto minmax(0,1fr);gap:9px;align-items:baseline}.si .jl .t{color:var(--txt-faint);font:500 12px ui-monospace,Menlo,monospace}" +
    ".si .bandeau{padding:10px 14px;border-radius:12px;font-size:13px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.si .bandeau .sp{flex:1;min-width:200px}.si .bandeau.da{background:color-mix(in srgb,var(--danger) 10%,transparent);color:var(--danger)}.si .bandeau.al{background:color-mix(in srgb,var(--warn) 12%,transparent);color:var(--warn)}.si .bandeau.in{background:color-mix(in srgb,var(--info,var(--accent)) 10%,transparent);color:var(--txt)}" +
    ".si .tete-s{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}.si .tete-s .sp{flex:1;min-width:220px}.si .tete-s h1{font:650 20px ui-monospace,'JetBrains Mono',Menlo,monospace;color:var(--txt-strong,var(--txt));overflow-wrap:anywhere}" +
    ".si .acts{display:flex;gap:7px;flex-wrap:wrap;align-items:center}.si .pied-t{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;font-size:12.5px;color:var(--txt-soft)}" +
    ".si input[type=text],.si select,.kit-m input[type=text],.kit-m select,.kit-m textarea{font:13.5px 'Inter',system-ui,sans-serif;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 11px;max-width:100%}.kit-m textarea{width:100%;min-height:70px}.kit-m .champ{display:grid;gap:4px}.kit-m .champ label{font:600 12.5px 'Inter',sans-serif;color:var(--txt-soft)}" +
    ".si .grp{font:600 11px 'Inter',sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint);margin:10px 2px 2px}" +
    "@media (max-width:700px){.si .row,.si .row.c2,.si .row.c1{grid-template-columns:minmax(0,1fr)}.si .cote{align-items:flex-start;flex-direction:row;gap:10px}.si dl.g{grid-template-columns:110px minmax(0,1fr)}.si .nm b,.si .nm small{white-space:normal}.si .jl>div{grid-template-columns:auto minmax(0,1fr)}.si .jl>div>span:last-child{grid-column:1/-1}}";

  // L'état de l'écran vit hors de la scène : le shell redessine l'onglet à chaque ouverture, et les autres écrans (Panorama, Hébergement) ouvrent un site d'ici.
  const S = { page: "vue", sel: null, onglet: "apercu", vue: null, lu: 0, q: "", filtre: "", p: 1, jours: 30, heures: 24 * 30, jfam: "", fiche: null, histo: null, copies: null, erreur: "" };
  let R = null;
  const msg = (e) => String((e && e.message) || e || "erreur");
  const lire = async (cap, args) => { try { return await agir(cap, args || {}); } catch (e) { S.erreur = msg(e); return null; } };
  const geste = async (cap, args, ok) => { try { const r = await agir(cap, args || {}); if (ok) dire(ok, "ok"); return r === undefined ? true : r; } catch (e) { dire(msg(e), "err"); return false; } };
  const z = (n) => String(n).padStart(2, "0");
  const heure = (ts) => { if (!ts) return "—"; const d = new Date(ts * 1000), a = new Date(); const hm = z(d.getHours()) + ":" + z(d.getMinutes()); return d.toDateString() === a.toDateString() ? hm : z(d.getDate()) + "/" + z(d.getMonth() + 1) + " " + hm; };
  const pct = (v) => (v == null ? "—" : (Math.round(v * 100) / 100).toLocaleString("fr-FR") + " %");
  const nb = (v) => Number(v).toLocaleString("fr-FR");
  const admin = () => !!(S.vue && S.vue.portee && S.vue.portee.admin);
  const moi = () => (S.vue && S.vue.portee && S.vue.portee.compte) || "";

  function etat(s) {
    if (s.up == null) return ["pas encore relevé", "", 1];
    if (s.up === false) return ["en panne · " + (s.code ? "code " + s.code : "ne répond pas"), "dg", 0];
    if (typeof s.ssl_jours === "number" && s.ssl_jours < 0) return ["certificat échu", "dg", 0];
    if (typeof s.ssl_jours === "number" && s.ssl_jours < 21) return ["certificat " + s.ssl_jours + " j", "al", 1];
    return ["en ligne", "ok", 2];
  }
  function pastilles(s) {
    const e = etat(s), p = [K.pill(e[0], e[1])];
    if (typeof s.ssl_jours === "number" && s.ssl_jours >= 21) p.push(K.pill("SSL " + s.ssl_jours + " j", "ok"));
    p.push(K.pill(s.source === "panneau" ? "panneau" : "hors panneau", ""));
    if (s.demande) p.push(K.pill("adossement demandé", "ac"));
    return p.join("");
  }
  const initiales = (d) => String(d || "").split(".")[0].slice(0, 2).toUpperCase() || "?";
  const sousTitre = (s) => [admin() ? ((s.comptes || []).join(", ") || (s.source === "panneau" ? "panneau · " + (s.proprietaire_panneau || "?") : "sans compte")) : "", s.php ? "PHP " + s.php : "", s.source === "panneau" ? "" : "déclaré à la main"].filter(Boolean).join(" · ") || "—";
  function ligne(s) {
    const d30 = s.dispo30;
    return '<button class="row" data-a="site" data-d="' + esc(s.domaine) + '"><span class="vg' + (s.up === false ? " dg" : "") + '">' + esc(initiales(s.domaine)) + '</span><span class="nm"><b class="mono">' + esc(s.domaine) + "</b><small>" + esc(sousTitre(s)) + '</small><span class="pills">' + pastilles(s) + "</span></span>" +
      '<span class="note">' + (d30 ? d30.pannes + " coupure" + (d30.pannes > 1 ? "s" : "") + (d30.indisponible_min ? " · " + esc(d30.indisponible) : "") + " sur 30 j" : "pas encore de mesure") + '</span><span class="cote"><span>' + pct(d30 && d30.disponibilite) + " · 30 j</span><span>" + (s.code == null ? "—" : s.code) + " · " + (s.ms == null ? "—" : nb(s.ms) + " ms") + "</span></span></button>";
  }
  function vigilance(v) {
    const n = v.niveau === "panne" ? ["grave", "dg"] : v.niveau === "regarder" ? ["à regarder", "al"] : ["info", ""];
    let b = "";
    if (v.geste === "repondre_demande") b = '<button class="btn mini pri" data-a="repondre" data-id="' + esc(v.demande) + '" data-v="fait">Adossé, c’est fait</button><button class="btn mini" data-a="repondre" data-id="' + esc(v.demande) + '" data-v="refusee">Refuser…</button>';
    else if (v.geste === "attribuer") b = '<button class="btn mini" data-a="attribuer" data-d="' + esc(v.site) + '">Attribuer…</button>';
    else if (v.geste === "demander") b = '<button class="btn mini" data-a="demander" data-d="' + esc(v.site) + '">Demander l’adossement</button>';
    return '<div class="row c2">' + K.pill(n[0], n[1]) + '<button class="nm" data-a="site" data-d="' + esc(v.site) + '" style="background:none;border:0;padding:0;text-align:left;color:inherit;font:inherit;cursor:pointer"><b>' + esc(v.titre) + "</b><small>" + esc(v.detail || "") + '</small></button><span class="acts">' + b + "</span></div>";
  }
  function journalHtml(lignes, avecSite) {
    if (!lignes || !lignes.length) return '<p class="note">Aucun geste encore.</p>';
    return '<div class="jl">' + lignes.map((l) => '<div><span class="t">' + esc(heure(l.ts)) + "</span>" + K.pill(VERBES[l.verbe] || l.verbe, l.verbe === "panne" ? "dg" : l.verbe === "retour" ? "ok" : "") + "<span>" + (avecSite ? '<a data-a="site" data-d="' + esc(l.domaine) + '" class="mono" style="cursor:pointer">' + esc(l.domaine) + "</a> · " : "") + esc(l.detail || "") + (l.detail ? " · " : "") + esc(l.acteur === "sonde" ? "la veille" : String(l.acteur || "").split("@")[0]) + "</span></div>").join("") + "</div>";
  }
  const entete = (acts) => K.titre(PAGES[S.page] || "Sites", SOUS[S.page] || "", acts || "");
  const bandeaux = () => (S.erreur ? '<div class="bandeau da"><div class="sp">' + esc(S.erreur) + '</div><button class="btn mini" data-a="recharger">Réessayer</button></div>' : "") +
    (S.vue && S.vue.portee && S.vue.portee.panneau_lu === false ? '<div class="bandeau in"><div class="sp">Le panneau ne répond pas ou n’est pas installé : seuls les sites déclarés, attribués ou inscrits dans une fiche sont montrés.</div></div>' : "");

  async function chargerVue(force) {
    if (!force && S.vue && Date.now() - S.lu < 30000) return S.vue;
    S.erreur = "";
    const v = await lire("sites.vue");
    if (v) { S.vue = v; S.lu = Date.now(); }
    return S.vue;
  }

  // ── les pages ───────────────────────────────────────────────────────────────────────────────────────
  const P = {
    async vue() {
      const v = await chargerVue();
      if (!v) return entete() + bandeaux();
      const l = v.sites || [], vig = v.vigilances || [], bas = l.filter((s) => s.up === false), graves = vig.filter((x) => x.niveau === "panne"), moy = vig.filter((x) => x.niveau === "regarder");
      const m = graves.length ? "dg" : moy.length ? "al" : "";
      const titre = !l.length ? (v.portee.admin ? "Aucun site connu" : "Aucun site dans ta portée") : bas.length ? (bas.length === 1 ? "Un site ne répond pas : " + bas[0].domaine : bas.length + " sites ne répondent pas") : graves.length ? graves[0].titre : moy.length ? l.length + " site" + (l.length > 1 ? "s répondent" : " répond") + " · " + moy.length + " point" + (moy.length > 1 ? "s" : "") + " à regarder" : (l.length > 1 ? "Les " + l.length + " sites répondent" : "Le site répond");
      const sous = !l.length ? "« Déclarer un site » en ajoute un ; un administrateur peut aussi t’en attribuer." : (graves.length || moy.length) ? vig.filter((x) => x.niveau !== "info").slice(0, 2).map((x) => x.titre).join(" ; ") + "." : "Aucune panne, aucun certificat court.";
      const mes = l.filter((s) => s.dispo30), dm = mes.length ? mes.reduce((a, s) => a + s.dispo30.disponibilite, 0) / mes.length : null;
      const certs = l.filter((s) => typeof s.ssl_jours === "number"), cmin = certs.length ? Math.min.apply(null, certs.map((s) => s.ssl_jours)) : null;
      const dem = l.filter((s) => s.demande).length;
      const stat = (lib, val, note, cl, a, f) => '<button class="stat ' + (cl || "") + '" data-a="' + a + '"' + (f != null ? ' data-f="' + f + '"' : "") + ' style="cursor:pointer"><b>' + val + "</b><span>" + lib + '</span><span class="note">' + note + "</span></button>";
      const j = await lire("sites.journal", { limite: 10 });
      return entete('<button class="btn" data-a="recharger">Relever</button><button class="btn pri" data-a="declarer">Déclarer un site</button>') + bandeaux() +
        '<div class="carte"><div class="verdict"><div class="vm ' + m + '"></div><div><p class="vt">' + esc(titre) + '</p><p class="note">' + esc(sous) + "</p></div></div>" +
        '<div class="stats">' + stat("En ligne", l.filter((s) => s.up).length + " / " + l.filter((s) => s.up != null).length, bas.length ? bas.length + " en panne" : "tous répondent", bas.length ? "al" : "", "aller-sites", bas.length ? "tombes" : "") +
        stat("Disponibilité 30 j", pct(dm), mes.length + " site" + (mes.length > 1 ? "s" : "") + " mesuré" + (mes.length > 1 ? "s" : ""), "", "aller", "dispo") +
        stat("Certificats", cmin == null ? "—" : cmin < 0 ? "échu" : cmin + " j", cmin == null ? "pas encore lus" : "le plus court · Sécurité › Certificats", cmin != null && cmin < 21 ? "al" : "", "certificats") +
        stat("Alertes", graves.length + moy.length, graves.length + " grave" + (graves.length > 1 ? "s" : "") + " · " + moy.length + " à regarder", graves.length || moy.length ? "al" : "", "aller", "alertes") +
        stat("Demandes", dem, v.portee.admin ? "adossement à traiter" : "en attente", dem ? "al" : "", "aller", "demandes") + "</div></div>" +
        '<div class="carte"><h3>Ce qui demande un geste</h3>' + (vig.length ? '<div class="rows">' + vig.slice(0, 5).map(vigilance).join("") + "</div>" + (vig.length > 5 ? '<button class="btn mini" data-a="aller" data-f="alertes" style="align-self:flex-start">Toutes les alertes</button>' : "") : '<p class="note"><b>Rien ne demande un geste.</b></p>') + "</div>" +
        '<div class="g2"><div class="carte"><h3>Les plus fragiles</h3><p class="note">disponibilité sur 30 jours</p>' + (mes.length ? '<div class="rows">' + mes.slice().sort((a, b) => a.dispo30.disponibilite - b.dispo30.disponibilite).slice(0, 4).map((s) => '<button class="row c1" data-a="site" data-d="' + esc(s.domaine) + '" data-o="dispo"><span class="nm"><b class="mono">' + esc(s.domaine) + "</b><small>" + s.dispo30.pannes + " coupure" + (s.dispo30.pannes > 1 ? "s" : "") + '</small></span><span class="cote">' + pct(s.dispo30.disponibilite) + "</span></button>").join("") + "</div>" : '<p class="note">Pas encore de mesure.</p>') + "</div>" +
        '<div class="carte"><h3>Derniers événements</h3>' + journalHtml(j && j.lignes ? j.lignes.slice(0, 5) : [], true) + '<button class="btn mini" data-a="aller" data-f="journal" style="align-self:flex-start">Tout le journal</button></div></div>' +
        '<div class="carte"><h3>D’où viennent les chiffres</h3><div class="liste">' +
        '<div class="li">' + K.pill("sonde", "ok") + '<div class="sp"><b>La sonde de Sites</b><span class="note">code et durée de réponse, toutes les 5 minutes</span></div><span class="note">' + esc(heure(Math.max.apply(null, l.map((s) => s.mesure || 0).concat([0])))) + "</span></div>" +
        '<div class="li">' + K.pill("certificats", "ok") + '<div class="sp"><b>Le module Certificats</b><span class="note">échéance, quota, renouvellement : Sites les lit, ne les refait pas</span></div><button class="btn mini" data-a="certificats">Ouvrir</button></div>' +
        '<div class="li">' + K.pill(v.portee.panneau_lu === false ? "absent" : "panneau", v.portee.panneau_lu === false ? "al" : "") + '<div class="sp"><b>FastPanel, facultatif</b><span class="note">' + (v.portee.panneau_lu === false ? "pas lu : Sites s’en passe" : "le propriétaire du panneau, PHP, les copies de sauvegarde") + "</span></div></div></div></div>";
    },

    async sites() {
      const v = await chargerVue();
      if (!v) return entete() + bandeaux();
      let l = (v.sites || []).slice();
      const q = S.q.trim().toLowerCase(), F = { tombes: (s) => s.up === false, regarder: (s) => etat(s)[2] < 2, panneau: (s) => s.source === "panneau", declares: (s) => s.source !== "panneau", sans: (s) => !(s.comptes || []).length };
      if (q) l = l.filter((s) => (s.domaine + " " + (s.comptes || []).join(" ") + " " + (s.proprietaire_panneau || "")).toLowerCase().includes(q));
      if (F[S.filtre]) l = l.filter(F[S.filtre]);
      l.sort((a, b) => etat(a)[2] - etat(b)[2] || ((a.dispo30 ? a.dispo30.disponibilite : 101) - (b.dispo30 ? b.dispo30.disponibilite : 101)) || a.domaine.localeCompare(b.domaine));
      const np = Math.max(1, Math.ceil(l.length / PAR)); S.p = Math.min(S.p, np);
      const page = l.slice((S.p - 1) * PAR, S.p * PAR);
      let corps;
      if (!l.length) corps = '<div class="vide"><b>Aucun site</b><p class="note">' + (v.sites.length ? "pour ce filtre." : "« Déclarer un site » en ajoute un.") + "</p></div>";
      else if (v.portee.admin) { const g = {}; page.forEach((s) => { const k = (s.comptes || []).join(", ") || (s.source === "panneau" ? "panneau · " + (s.proprietaire_panneau || "?") + " (sans compte Cassandra)" : "sans compte"); (g[k] = g[k] || []).push(s); }); corps = Object.keys(g).sort().map((k) => '<div class="grp">' + esc(k) + " · " + g[k].length + '</div><div class="rows">' + g[k].map(ligne).join("") + "</div>").join(""); }
      else corps = '<div class="rows">' + page.map(ligne).join("") + "</div>";
      const chips = [["", "tous"], ["tombes", "en panne"], ["regarder", "à regarder"], ["panneau", "du panneau"], ["declares", "déclarés"]].concat(v.portee.admin ? [["sans", "sans compte"]] : []);
      return entete('<button class="btn pri" data-a="declarer">Déclarer un site</button>') + bandeaux() +
        '<div class="carte"><div class="barre"><input type="search" data-q placeholder="Chercher un site' + (v.portee.admin ? ", un compte" : "") + '" aria-label="Chercher" value="' + esc(S.q) + '"></div>' +
        '<div class="chips">' + chips.map((c) => '<button class="chip" data-a="filtre" data-f="' + c[0] + '"' + (S.filtre === c[0] ? ' style="background:var(--accent);color:var(--on-accent,#fff);border-color:transparent"' : "") + ' aria-pressed="' + (S.filtre === c[0]) + '">' + c[1] + "</button>").join("") + "</div>" + corps +
        (l.length > PAR ? '<div class="pied-t"><span>' + ((S.p - 1) * PAR + 1) + "–" + Math.min(l.length, S.p * PAR) + " sur " + l.length + '</span><span class="acts"><button class="btn mini" data-a="page" data-p="' + (S.p - 1) + '"' + (S.p > 1 ? "" : " disabled") + '>‹ précédents</button><button class="btn mini" data-a="page" data-p="' + (S.p + 1) + '"' + (S.p < np ? "" : " disabled") + ">suivants ›</button></span></div>" : "") + "</div>";
    },

    async alertes() {
      const v = await chargerVue();
      if (!v) return entete() + bandeaux();
      const vig = v.vigilances || [], j = await lire("sites.journal", { limite: 200 });
      const coup = ((j && j.lignes) || []).filter((x) => ["panne", "retour", "decouverte"].includes(x.verbe)).slice(0, 40);
      return entete() + bandeaux() + '<div class="carte"><h3>' + vig.filter((x) => x.niveau !== "info").length + " alerte(s) · " + vig.filter((x) => x.niveau === "info").length + " pour information</h3>" + (vig.length ? '<div class="rows">' + vig.map(vigilance).join("") + "</div>" : '<p class="note"><b>Rien ne demande un geste.</b></p>') + "</div>" +
        '<div class="carte"><h3>Coupures et retours</h3>' + journalHtml(coup, true) + "</div>";
    },

    async dispo() {
      const d = await lire("sites.disponibilite", { jours: S.jours });
      const seg = '<div class="seg" role="group" aria-label="Période">' + [7, 30, 90].map((n) => '<button class="' + (S.jours === n ? "on" : "") + '" data-a="jours" data-n="' + n + '">' + n + " jours</button>").join("") + "</div>";
      if (!d) return entete(seg) + bandeaux();
      const l = (d.sites || []).slice().sort((a, b) => a.disponibilite - b.disponibilite);
      return entete(seg) + bandeaux() + '<div class="carte">' + (l.length ? '<div class="rows">' + l.map((s) => '<button class="row" data-a="site" data-d="' + esc(s.domaine) + '" data-o="dispo"><span class="vg' + (s.en_panne ? " dg" : "") + '">' + esc(initiales(s.domaine)) + '</span><span class="nm"><b class="mono">' + esc(s.domaine) + "</b><small>" + s.mesures + " mesures" + (s.en_panne ? " · en panne en ce moment" : "") + '</small></span><span class="note">' + s.pannes + " coupure" + (s.pannes > 1 ? "s" : "") + (s.indisponible_min ? " · " + esc(s.indisponible) + " indisponible" : "") + '</span><span class="cote"><span><b style="color:var(--txt-strong,var(--txt))">' + pct(s.disponibilite) + "</b></span><span>" + (s.reponse_moy_ms == null ? "—" : nb(s.reponse_moy_ms) + " ms en moyenne") + "</span></span></button>").join("") + "</div>" : '<p class="note">' + esc(d.raison || "Aucune mesure.") + "</p>") +
        ((d.plus_suivis || []).length ? '<p class="note">Plus mesurés depuis deux jours, donc sans chiffre : ' + d.plus_suivis.map(esc).join(", ") + ".</p>" : "") + "</div>" +
        '<div class="carte"><h4>Comment c’est compté</h4><p class="note">Une mesure toutes les 5 minutes. Une panne se dit après plusieurs échecs de suite et commence au premier ; une panne qui dure encore compte jusqu’à maintenant. Un site qu’on ne mesure plus n’a pas 100 % : il n’a pas de chiffre.</p></div>';
    },

    async demandes() {
      const v = await chargerVue(), d = await lire("sites.demandes", { statut: "ouverte" });
      if (!v || !d) return entete() + bandeaux();
      const l = d.demandes || [];
      return entete() + bandeaux() + '<div class="carte"><h3>Adossement au panneau</h3>' + (l.length ? l.map((x) => '<div class="alerte al"><div class="sp"><b class="mono">' + esc(x.domaine) + '</b><span class="note">demandé par ' + esc(x.compte) + " · " + esc(heure(x.ts)) + (x.message ? " · « " + esc(x.message) + " »" : "") + "</span></div>" +
        (v.portee.admin ? '<button class="btn mini pri" data-a="repondre" data-id="' + x.id + '" data-v="fait">Adossé, c’est fait</button><button class="btn mini" data-a="repondre" data-id="' + x.id + '" data-v="refusee">Refuser…</button>' : "") + '<button class="btn mini" data-a="site" data-d="' + esc(x.domaine) + '">La page du site</button></div>').join("") : '<p class="note">Aucune demande ouverte.</p>') + "</div>";
    },

    async journal() {
      await chargerVue();
      const j = await lire("sites.journal", { limite: 200 });
      const l = ((j && j.lignes) || []).filter((x) => !S.jfam || FAM_DE(x.verbe) === S.jfam);
      return entete() + bandeaux() + '<div class="carte"><div class="chips">' + FAMILLES.map((f) => '<button class="chip" data-a="jfam" data-f="' + f[0] + '"' + (S.jfam === f[0] ? ' style="background:var(--accent);color:var(--on-accent,#fff);border-color:transparent"' : "") + ' aria-pressed="' + (S.jfam === f[0]) + '">' + f[1] + "</button>").join("") + "</div>" + journalHtml(l, true) + "</div>";
    },

    // ── la page d'un site ───────────────────────────────────────────────────────────────────────────────
    async site() {
      await chargerVue();
      const f = await lire("sites.fiche", { domaine: S.sel });
      const fil = '<p class="fil"><a data-a="aller" data-f="sites">‹ tous les sites</a></p>';
      if (!f) return fil + '<div class="carte vide"><b>Cette page ne s’ouvre pas</b><p class="note">' + esc(S.erreur || "site hors de ta portée") + "</p></div>";
      S.fiche = f; const s = f.site, e = etat(s), d = f.domaine;
      if (S.onglet === "heberg" && f.hors_panneau) S.onglet = "apercu";
      const acts = '<button class="btn" data-a="recharger">Relire</button>' + (f.gestes.demander ? '<button class="btn" data-a="demander" data-d="' + esc(d) + '">Demander l’adossement</button>' : "") + (f.gestes.transferer ? '<button class="btn" data-a="transferer" data-d="' + esc(d) + '">Transférer…</button>' : "") +
        (f.gestes.attribuer && !(s.comptes || []).length ? '<button class="btn" data-a="attribuer" data-d="' + esc(d) + '">Attribuer…</button>' : "") + (f.gestes.retirer ? '<button class="btn dng" data-a="retirer" data-d="' + esc(d) + '">Retirer de la liste</button>' : "");
      const tete = '<div class="carte"><div class="tete-s"><span class="vg gd' + (s.up === false ? " dg" : "") + '">' + esc(initiales(d)) + '</span><div class="sp"><h1>' + esc(d) + '</h1><div class="pills">' + pastilles(s) + '</div><p class="note" style="margin-top:6px">Propriétaire : <b>' + (f.mien ? "toi" : esc((s.comptes || []).join(", ") || "aucun compte Cassandra")) + "</b>" + (s.proprietaire_panneau ? " · compte « " + esc(s.proprietaire_panneau) + " » du panneau" : "") + '</p></div><div class="acts">' + acts + "</div></div>" +
        '<div class="onglets" role="tablist">' + ONGLETS.filter((o) => o[0] !== "heberg" || !f.hors_panneau).map((o) => '<button role="tab" class="' + (S.onglet === o[0] ? "on" : "") + '" aria-selected="' + (S.onglet === o[0]) + '" data-a="onglet" data-o="' + o[0] + '">' + o[1] + "</button>").join("") + "</div>";
      return fil + bandeaux() + tete + (await O[S.onglet](f, s, e)) + "</div>";
    },
  };

  // ── les onglets de la page d'un site ────────────────────────────────────────────────────────────────
  const O = {
    async apercu(f, s) {
      const h = f.histoire || {}, d30 = s.dispo30;
      return (f.admin_autrui ? '<div class="bandeau in"><div class="sp">Ce site appartient à ' + esc((s.comptes || []).join(", ") || "un compte du panneau") + ". Tu vois son état, pas son contenu.</div></div>" : "") +
        (f.demande ? '<div class="bandeau al"><div class="sp"><b>Adossement demandé</b> par ' + esc(f.demande.compte) + (f.demande.message ? " : « " + esc(f.demande.message) + " »" : "") + ".</div>" + (admin() ? '<button class="btn mini pri" data-a="repondre" data-id="' + f.demande.id + '" data-v="fait">Adossé, c’est fait</button><button class="btn mini" data-a="repondre" data-id="' + f.demande.id + '" data-v="refusee">Refuser…</button>' : "") + "</div>" : "") +
        '<dl class="g"><dt>réponse</dt><dd>' + (s.up == null ? '<span class="note">pas encore relevé : dans moins de 5 minutes</span>' : (s.code == null ? "sans réponse" : s.code) + " en " + nb(s.ms || 0) + ' ms <span class="note">' + esc(heure(s.mesure)) + (s.erreur ? " · " + esc(s.erreur) : "") + "</span>") + "</dd>" +
        "<dt>disponibilité 30 j</dt><dd>" + (d30 ? pct(d30.disponibilite) + " · " + d30.pannes + " coupure" + (d30.pannes > 1 ? "s" : "") + (d30.indisponible_min ? " · " + esc(d30.indisponible) : "") : '<span class="note">pas encore de mesure</span>') + "</dd>" +
        "<dt>dernières 24 h</dt><dd>" + (h.mesures ? pct(h.disponibilite) + " · " + (h.reponse_moy_ms == null ? "—" : nb(h.reponse_moy_ms) + " ms en moyenne") + " · " + h.mesures + " mesures" : '<span class="note">pas encore de mesure</span>') + "</dd>" +
        "<dt>certificat</dt><dd>" + (typeof s.ssl_jours === "number" ? (s.ssl_jours < 0 ? "échu depuis " + (-s.ssl_jours) + " j" : "expire dans " + s.ssl_jours + " j") + ' <span class="note">' + esc({ certificats: "d’après Certificats", sonde: "lu par la sonde", panneau: "d’après le panneau" }[s.ssl_source] || "") + '</span> <button class="btn mini" data-a="certificats">Certificats</button>' : '<span class="note">pas encore lu</span>') + "</dd>" +
        "<dt>hébergement</dt><dd>" + (f.hors_panneau ? "hors panneau, déclaré à la main" : "panneau · compte « " + esc(s.proprietaire_panneau || "?") + " »" + (s.php ? " · PHP " + esc(s.php) : "")) + "</dd></dl>" +
        (f.hors_panneau ? '<p class="note">Hors panneau : la sonde, l’historique, les rattachements et le journal.</p>' : '<div class="acts"><button class="btn" data-a="renouveler" data-d="' + esc(f.domaine) + '">Renouveler le certificat…</button><button class="btn" data-a="onglet" data-o="heberg">Copies de sauvegarde</button>' + (f.gestes.accorder ? '<button class="btn" data-a="accorder" data-d="' + esc(f.domaine) + '">Autoriser une restauration (24 h)</button>' : "") + "</div>") +
        (f.accord ? '<div class="bandeau in"><div class="sp">Accord de restauration donné par ' + esc(f.accord.par) + " jusqu’au " + esc(heure(f.accord.jusqu_a)) + ".</div></div>" : "") +
        "<h4>Derniers événements</h4>" + ((h.evenements || []).length ? '<div class="jl">' + h.evenements.map((x) => '<div><span class="t">' + esc(heure(x.ts)) + "</span>" + K.pill(VERBES[x.genre] || x.genre, x.genre === "panne" ? "dg" : x.genre === "retour" ? "ok" : "") + "<span>" + esc(x.detail || "") + "</span></div>").join("") + "</div>" : '<p class="note">Rien sur les dernières 24 heures.</p>');
    },
    async dispo(f) {
      const seg = '<div class="seg" role="group" aria-label="Période">' + [[24, "24 h"], [24 * 7, "7 jours"], [24 * 30, "30 jours"], [24 * 90, "90 jours"]].map((x) => '<button class="' + (S.heures === x[0] ? "on" : "") + '" data-a="heures" data-n="' + x[0] + '">' + x[1] + "</button>").join("") + "</div>";
      const h = await lire("sites.historique", { domaine: f.domaine, heures: S.heures });
      if (!h) return seg + bandeaux();
      // Un trait par jour (par heure sur 24 h) : le pire de la tranche l'emporte, une tranche sans mesure reste grise.
      const n = S.heures === 24 ? 24 : S.heures / 24, pas = S.heures === 24 ? 3600 : 86400, fin = Date.now() / 1000, cases = Array.from({ length: n }, () => ({ t: 0, bas: 0 }));
      (h.points || []).forEach((p) => { const k = n - 1 - Math.floor((fin - p.ts) / pas); if (k >= 0 && k < n) { cases[k].t++; if (!p.up) cases[k].bas++; } });
      const bande = '<div class="bande" role="img" aria-label="Disponibilité : ' + pct(h.disponibilite) + '">' + cases.map((c, i) => '<i class="' + (!c.t ? "n" : !c.bas ? "" : c.bas * 3 >= c.t ? "d" : "w") + '" title="' + (S.heures === 24 ? "il y a " + (n - 1 - i) + " h" : "il y a " + (n - 1 - i) + " j") + " : " + (!c.t ? "pas de mesure" : !c.bas ? "sans coupure" : c.bas + " mesure(s) en échec sur " + c.t) + '"></i>').join("") + "</div>";
      return seg + (h.mesures ? '<div class="stats"><div class="stat"><b>' + pct(h.disponibilite) + "</b><span>disponibilité</span></div><div class=\"stat\"><b>" + h.mesures + '</b><span>mesures</span></div><div class="stat"><b>' + (h.reponse_moy_ms == null ? "—" : nb(h.reponse_moy_ms) + " ms") + '</b><span>réponse moyenne</span></div><div class="stat"><b>' + (h.reponse_max_ms == null ? "—" : nb(h.reponse_max_ms) + " ms") + "</b><span>au pire</span></div></div>" + bande +
        '<div class="leg"><span><i style="background:var(--ok)"></i>sans coupure</span><span><i style="background:var(--warn)"></i>coupure courte</span><span><i style="background:var(--danger)"></i>coupure longue</span><span><i style="background:var(--line-strong,var(--line))"></i>pas de mesure</span></div>' : '<p class="note"><b>Pas encore de mesure</b> sur cette période. Le site n’a pas 100 % : il n’a pas de chiffre.</p>') +
        "<h4>Coupures et retours</h4>" + ((h.evenements || []).length ? '<div class="jl">' + h.evenements.slice(0, 30).map((x) => '<div><span class="t">' + esc(heure(x.ts)) + "</span>" + K.pill(VERBES[x.genre] || x.genre, x.genre === "panne" ? "dg" : x.genre === "retour" ? "ok" : "") + "<span>" + esc(x.detail || "") + "</span></div>").join("") + "</div>" : '<p class="note">Aucune sur cette période.</p>') +
        '<div class="acts"><button class="btn mini" data-a="courbes">Courbes détaillées (Historique)</button></div>';
    },
    async heberg(f, s) {
      const c = S.copies && S.copies.d === f.domaine ? S.copies : null, peut = f.mien || !!f.accord;
      return '<h4>Copies de sauvegarde</h4><p class="note">Une copie couvre tout le compte du panneau, pas ce seul site. La restaurer demande d’être le propriétaire, ou son accord.</p>' +
        (!c ? '<div class="acts"><button class="btn" data-a="copies" data-d="' + esc(f.domaine) + '">Voir les copies</button></div>' : c.erreur ? '<div class="bandeau al"><div class="sp">' + esc(c.erreur) + "</div></div>" : (c.l.length ? '<div class="rows">' + c.l.map((x) => '<div class="row c2">' + K.pill(x.partielle ? "partielle" : "complète", x.partielle ? "al" : "ok") + '<span class="nm"><b>' + esc(String(x.debut || "").replace("T", " ").slice(0, 16)) + "</b><small>" + (x.compte ? "compte " + esc(x.compte) + " · " : "") + (x.octets ? nb(Math.round(x.octets / 1048576)) + " Mo" : "") + ((x.bases || []).length ? " · bases : " + esc(x.bases.join(", ")) : "") + '</small></span><button class="btn mini dng" data-a="restaurer" data-d="' + esc(f.domaine) + '" data-id="' + esc(x.id) + '"' + (peut ? "" : ' disabled title="accord du propriétaire requis"') + ">Restaurer</button></div>").join("") + "</div>" : '<p class="note">Aucune copie pour ce compte.</p>')) +
        (f.accord ? '<div class="bandeau in"><div class="sp">Accord de restauration donné par ' + esc(f.accord.par) + " jusqu’au " + esc(heure(f.accord.jusqu_a)) + ".</div></div>" : f.gestes.accorder ? '<div class="acts"><button class="btn" data-a="accorder" data-d="' + esc(f.domaine) + '">Autoriser l’administrateur à restaurer (24 h)</button></div>' : "") +
        '<h4>Dans Hébergement</h4><p class="note">Le disque, les bases, le DNS et le courrier de ce site se lisent dans Hébergement' + (admin() ? "" : ", réservé aux administrateurs") + ".</p>" + (admin() ? '<div class="acts"><button class="btn mini" data-a="hebergement" data-d="' + esc(f.domaine) + '">Ouvrir Hébergement</button></div>' : "");
    },
    async liens(f) {
      const l = f.liens || [], lib = (g) => (GENRES.find((x) => x[0] === g) || [g, g])[1];
      return '<p class="note">Un projet, un contact, une machine ou une note rattachés à ce site.</p>' + (l.length ? '<div class="rows">' + l.map((x) => '<div class="row c2">' + K.pill(lib(x.genre), "") + '<span class="nm"><b>' + esc(x.ref) + "</b><small>" + esc(x.note || "") + (x.note ? " · " : "") + esc(heure(x.ts)) + '</small></span><button class="btn mini" data-a="delier" data-d="' + esc(f.domaine) + '" data-g="' + esc(x.genre) + '" data-r="' + esc(x.ref) + '">Retirer</button></div>').join("") + "</div>" : '<p class="note">Aucun rattachement.</p>') +
        '<div class="acts"><button class="btn" data-a="lier" data-d="' + esc(f.domaine) + '">Rattacher…</button></div>';
    },
    async journal(f) { return journalHtml(f.journal, false) + '<div class="acts"><button class="btn mini" data-a="aller" data-f="journal">Tout le journal</button></div>'; },
  };

  // ── une petite fenêtre (les classes kit-v / kit-m du kit) ───────────────────────────────────────────
  function fenetre(titre, corps, oui, danger) {
    return new Promise((fin) => {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
      const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titre);
      m.innerHTML = "<h2>" + esc(titre) + "</h2>" + corps + '<div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn ' + (danger ? "dng" : "pri") + '" data-c="oui">' + esc(oui) + "</button></div>";
      const clore = (r) => { v.remove(); m.remove(); fin(r); };
      v.addEventListener("click", () => clore(null));
      m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b) clore(b.dataset.c === "oui" ? m : null); });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(null); if (e.key === "Enter" && e.target.tagName === "INPUT") clore(m); });
      document.body.appendChild(v); document.body.appendChild(m);
      const f = m.querySelector("input,select,textarea,[data-c]"); if (f) f.focus();
    });
  }
  const val = (m, sel) => String((m.querySelector(sel) || {}).value || "").trim();
  const champ = (lib, html, aide) => '<div class="champ"><label>' + esc(lib) + "</label>" + html + (aide ? '<span class="note">' + esc(aide) + "</span>" : "") + "</div>";
  const poster = async (route, corps) => { if (typeof window.apiPost !== "function") throw new Error("route indisponible"); return window.apiPost(route, corps); };

  // ── les gestes ──────────────────────────────────────────────────────────────────────────────────────
  const A = {
    aller: (b) => aller(b.dataset.f),
    "aller-sites": (b) => { S.filtre = b.dataset.f || ""; S.p = 1; aller("sites"); },
    site: (b) => ouvrir(b.dataset.d, b.dataset.o),
    onglet: (b) => { S.onglet = b.dataset.o; rendre(); },
    filtre: (b) => { S.filtre = b.dataset.f; S.p = 1; rendre(); },
    page: (b) => { S.p = Math.max(1, +b.dataset.p || 1); rendre(); },
    jours: (b) => { S.jours = +b.dataset.n; rendre(); },
    heures: (b) => { S.heures = +b.dataset.n; rendre(); },
    jfam: (b) => { S.jfam = b.dataset.f; rendre(); },
    recharger: async () => { S.lu = 0; S.copies = null; await rendre(); },
    certificats: () => { if (CASS.ouvrirEcran) CASS.ouvrirEcran("certificats:c_liste", "Certificats"); },
    courbes: () => { try { MX.demande = "site_up"; } catch (e) { /* l'Historique s'ouvrira sur sa page d'accueil */ } window.switchTab("history"); },
    hebergement: (b) => { if (typeof window.fpVersSite === "function") window.fpVersSite(b.dataset.d, "domains"); else window.switchTab("fastpanel"); },
    async declarer() {
      const m = await fenetre("Déclarer un site", champ("Nom du site", '<input type="text" data-n placeholder="mon-site.exemple.fr" autocomplete="off">', "Le nom nu : « www. », le protocole et le chemin sont retirés. Un site du panneau ne se déclare pas : il s’attribue."), "Déclarer");
      if (!m) return; const r = await geste("sites.declarer", { domaine: val(m, "[data-n]") }, "Site déclaré : la sonde le suit à son prochain tour.");
      if (r) { S.lu = 0; if (r.domaine) ouvrir(r.domaine); else rendre(); }
    },
    async retirer(b) { if (await K.confirmer("Retirer " + b.dataset.d, '<p class="note">La sonde cesse de le suivre ; son historique reste. Ses rattachements sont mis de côté, ses accords tombent, sa demande ouverte se ferme.</p>', "Retirer", true) && await geste("sites.retirer", { domaine: b.dataset.d }, "Site retiré.")) { S.lu = 0; aller("sites"); } },
    async attribuer(b) { const m = await fenetre("Attribuer " + b.dataset.d, champ("Compte Cassandra", '<input type="text" data-n placeholder="nom@exemple.fr" autocomplete="off">', "Il recevra la vue et le journal de ce site."), "Attribuer"); if (m && await geste("sites.attribuer", { domaine: b.dataset.d, compte: val(m, "[data-n]") }, "Site attribué.")) { S.lu = 0; rendre(); } },
    async transferer(b) { const m = await fenetre("Transférer " + b.dataset.d, champ("Compte destinataire", '<input type="text" data-n placeholder="nom@exemple.fr" autocomplete="off">', "L’ancien propriétaire ne le verra plus. Ses rattachements, ses accords et sa demande ne suivent pas."), "Transférer"); if (m && await geste("sites.transferer", { domaine: b.dataset.d, vers: val(m, "[data-n]") }, "Site transféré.")) { S.lu = 0; rendre(); } },
    async demander(b) { const m = await fenetre("Demander l’adossement de " + b.dataset.d, champ("Un mot pour l’administrateur (facultatif)", "<textarea data-n></textarea>", "Ce que le site héberge, où il est aujourd’hui."), "Envoyer la demande"); if (m && await geste("sites.demander", { domaine: b.dataset.d, message: val(m, "[data-n]") }, "Demande envoyée à l’administrateur.")) { S.lu = 0; rendre(); } },
    async repondre(b) {
      const fait = b.dataset.v === "fait";
      const m = fait ? (await K.confirmer("Adossement fait", '<p class="note">Le site est adossé dans le panneau : la demande se ferme et le compte est prévenu.</p>', "Confirmer") ? document.createElement("div") : null) : await fenetre("Refuser la demande", champ("La raison, telle que le compte la lira", "<textarea data-n></textarea>"), "Refuser", true);
      if (m && await geste("sites.repondre_demande", { id: +b.dataset.id, decision: fait ? "fait" : "refusee", reponse: val(m, "[data-n]") }, fait ? "Demande close : adossé." : "Demande refusée.")) { S.lu = 0; rendre(); }
    },
    async accorder(b) { if (await K.confirmer("Accord de restauration", '<p class="note">Autorise un administrateur à restaurer une sauvegarde sur ' + esc(b.dataset.d) + " pendant 24 heures. L’accord tombe si le site change de compte.</p>", "Donner l’accord") && await geste("sites.accorder", { domaine: b.dataset.d, geste: "restaurer", heures: 24 }, "Accord donné pour 24 heures.")) rendre(); },
    async lier(b) { const m = await fenetre("Rattacher à " + b.dataset.d, champ("Type", '<select data-g>' + GENRES.map((g) => '<option value="' + g[0] + '">' + g[1] + "</option>").join("") + "</select>") + champ("Référence", '<input type="text" data-n autocomplete="off">', "Le nom ou l’identifiant.") + champ("Note (facultative)", '<input type="text" data-t autocomplete="off">'), "Rattacher"); if (m && await geste("sites.lier", { domaine: b.dataset.d, genre: val(m, "[data-g]"), ref: val(m, "[data-n]"), note: val(m, "[data-t]") }, "Rattaché.")) rendre(); },
    async delier(b) { if (await geste("sites.delier", { domaine: b.dataset.d, genre: b.dataset.g, ref: b.dataset.r }, "Lien retiré.")) rendre(); },
    async copies(b) { let r; try { r = await poster("/api/site/copies", { domain: b.dataset.d }); } catch (e) { r = { ok: false, reason: msg(e) }; } S.copies = r && r.ok ? { d: b.dataset.d, l: r.copies || [] } : { d: b.dataset.d, l: [], erreur: (r && (r.reason || r.error)) || "copies indisponibles" }; rendre(); },
    async restaurer(b) {
      let r; try { r = await poster("/api/site/restaurer", { domain: b.dataset.d, copie: b.dataset.id }); } catch (e) { return dire(msg(e), "err"); }
      if (r && r.needs_confirm) { if (!await K.confirmer("Restaurer une sauvegarde", '<p class="note">' + esc(r.reason || "") + "</p>", "Restaurer", true)) return; try { r = await poster("/api/site/restaurer", { domain: b.dataset.d, copie: b.dataset.id, confirm: true }); } catch (e) { return dire(msg(e), "err"); } }
      dire(r && r.ok ? "Restauration lancée par le panneau." : (r && (r.reason || r.error)) || "refusé", r && r.ok ? "ok" : "err");
    },
    async renouveler(b) {
      let r; try { r = await poster("/api/sites/act", { domain: b.dataset.d, action: "ssl_renew" }); } catch (e) { return dire(msg(e), "err"); }
      if (r && r.needs_confirm) { if (!await K.confirmer("Renouveler le certificat", '<p class="note">' + esc(r.reason || "") + "</p>", "Renouveler")) return; try { r = await poster("/api/sites/act", { domain: b.dataset.d, action: "ssl_renew", confirm: true }); } catch (e) { return dire(msg(e), "err"); } }
      dire((r && (r.message || r.error || r.reason)) || (r && r.ok ? "fait" : "refusé"), r && r.ok ? "ok" : "err"); if (r && r.ok) { S.lu = 0; rendre(); }
    },
  };

  // ── le rendu et la navigation ───────────────────────────────────────────────────────────────────────
  let tour = 0, dernier = null;
  async function rendre() {
    if (!R || !document.body.contains(R)) return;
    const moi_ = ++tour, page = P[S.page] ? S.page : "vue";
    if (!R.innerHTML) R.innerHTML = '<div class="carte"><p class="note">Lecture des sites…</p></div>';
    S.erreur = "";
    let html;
    try { html = await P[page](); } catch (e) { html = '<div class="bandeau da"><div class="sp">' + esc(msg(e)) + '</div><button class="btn mini" data-a="recharger">Réessayer</button></div>'; }
    if (moi_ !== tour || !R) return;                                // une navigation plus récente a pris la main
    const q = R.querySelector("[data-q]"), foyer = q && document.activeElement === q;
    R.innerHTML = html; dernier = { page: S.page, sel: S.sel, onglet: S.onglet, html: html };
    if (foyer) { const n = R.querySelector("[data-q]"); if (n) { n.focus(); try { n.setSelectionRange(n.value.length, n.value.length); } catch (e) {} } }
  }
  function aller(page) { S.page = P[page] && page !== "site" ? page : "vue"; S.sel = null; S.p = 1; rendre(); const sc = R && R.closest(".tab-content"); if (sc && sc.scrollIntoView) window.scrollTo(0, 0); }
  function ouvrir(domaine, onglet) { S.page = "site"; S.sel = String(domaine || "").toLowerCase().replace(/^www\./, ""); S.onglet = ONGLETS.some((o) => o[0] === onglet) ? onglet : "apercu"; S.copies = null; rendre(); window.scrollTo(0, 0); }
  const actif = () => { const t = document.getElementById("tab-mysites"); return !!(t && t.classList.contains("active")); };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.sites = async function (corps) {
    K.injecter();
    if (!document.getElementById("si-css")) { const st = document.createElement("style"); st.id = "si-css"; st.textContent = CSS; document.head.appendChild(st); }
    const titre = corps.parentElement && corps.parentElement.querySelector(".sh-titre"); if (titre) titre.style.display = "none";      // chaque page a son propre titre
    corps.innerHTML = ""; R = document.createElement("div"); R.className = "kit si"; corps.appendChild(R);
    // Le shell redessine l'onglet à chaque retour sur l'écran : on remet tout de suite ce qu'on montrait, puis on relit. Sans cela la page clignotait sur « Lecture des sites… ».
    if (dernier && dernier.page === S.page && dernier.sel === S.sel && dernier.onglet === S.onglet && !window.__stVue) R.innerHTML = dernier.html;
    R.addEventListener("click", (e) => { const b = e.target.closest("[data-a]"); if (!b || b.disabled) return; const f = A[b.dataset.a]; if (f) { e.preventDefault(); Promise.resolve(f(b)).catch((x) => dire(msg(x), "err")); } });
    R.addEventListener("input", (e) => { if (e.target.matches("[data-q]")) { S.q = e.target.value; S.p = 1; rendre(); } });
    const v = window.__stVue; window.__stVue = null;
    if (v) { S.page = P[v] && v !== "site" ? v : "vue"; S.sel = null; }
    await rendre();
  };

  // Ce que le menu de gauche et les autres écrans appellent (les noms de l'ancien écran sont gardés : Panorama, Hébergement et l'Historique s'en servent).
  window.stVue = function (vue) { if (R && document.body.contains(R)) aller(vue || "vue"); else window.__stVue = vue || "vue"; };
  window.loadMySites = function (force) { if (force) S.lu = 0; if (R && document.body.contains(R)) return rendre(); };      // sans « force », la vue lue il y a moins de trente secondes sert encore
  window.stOpen = function (domaine) { if (!actif() && typeof window.switchTab === "function") { S.page = "site"; S.sel = String(domaine || "").toLowerCase().replace(/^www\./, ""); S.onglet = "apercu"; window.switchTab("mysites"); return; } ouvrir(domaine); };
  window.stFiltre = function (f) { S.filtre = { tombes: "tombes", regarder: "regarder", panneau: "panneau", declares: "declares", sans: "sans" }[f] || ""; S.p = 1; if (R && document.body.contains(R)) aller("sites"); else window.__stVue = "sites"; };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
