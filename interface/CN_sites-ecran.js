// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Sites : l'écran du module
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #54081c
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine les pages du module sites (vue d'ensemble, tous les sites, la page d'un site, alertes, disponibilité, demandes, journal) ; ses pages sont les sous-entrées de « Sites » dans le menu de gauche
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.sites) qui remplace l'onglet V18 « mysites » ; tout vient des capacités sites.* ; l'état vit hors de la scène, car le shell la redessine à chaque ouverture ; window.stVue reçoit la page demandée par le menu, window.stOpen ouvre un site depuis un autre écran
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=54081c ▼▼▼
// Sites : l'écran du module. Il remplace l'onglet V18 « mysites » ; ses pages sont les sous-menus de « Sites » dans le menu de gauche
// (le rail interne de l'ancien écran a disparu). Lot 1 : ce que les capacités sites.* savaient déjà rendre. Lot 2 : les incidents (une panne est un objet
// qu'on dépanne), le calendrier d'un site, les sociétés, la preuve de propriété, les objectifs et les réglages.
(function () {
  "use strict";
  const CASS = window.CASS;
  const K = CASS.kit;
  const esc = K.esc, agir = K.agir, dire = K.dire;
  const PAGES = { vue: "Vue d’ensemble", sites: "Tous les sites", incidents: "Incidents", alertes: "Alertes", dispo: "Disponibilité", calendrier: "Calendrier", demandes: "Demandes et preuves", journal: "Journal", reglages: "Réglages" };
  const SOUS = {
    vue: "L’état de tes sites, ce qui demande un geste, et d’où viennent les chiffres.",
    sites: "Le pire d’abord. Un clic ouvre la page d’un site.",
    incidents: "Une panne est un objet : un diagnostic, des actions, une chronologie, une cause.",
    alertes: "Ce qui demande un geste, puis les coupures et les retours.",
    dispo: "La part du temps où chaque site a répondu, face à son objectif.",
    calendrier: "Tout ce qui est arrivé à un site, jour par jour.",
    demandes: "Les demandes d’adossement au panneau, les preuves de propriété en attente, les accords en cours.",
    journal: "Les gestes faits sur les sites et ce que la veille a vu, fondus.",
    reglages: "Ce que l’écran appelle une panne, et ce que chacun — agents compris — peut faire sur les sites.",
  };
  const ONGLETS = [["apercu", "Aperçu"], ["dispo", "Disponibilité"], ["heberg", "Hébergement"], ["liens", "Liens"], ["journal", "Journal"]];
  const VERBES = { declare: "déclaré", declare_annule: "déclaration annulée", declare_a_prouver: "déclaré, à prouver", prouve: "propriété prouvée", retire: "retiré", attribue: "attribué", transfere: "transféré", demande: "adossement demandé", adossement_fait: "adossé", adossement_refuse: "adossement refusé",
    accord: "accord donné", lien: "rattaché", delie: "lien retiré", panne: "coupure", retour: "de retour", decouverte: "découvert", societe: "société attribuée", objectif: "objectif posé", incident_pris: "incident pris en charge", incident_clos: "incident clos" };
  const FAMILLES = [["", "tout"], ["coupures", "coupures et incidents"], ["gestes", "gestes"], ["demandes", "demandes, preuves et accords"]];
  const FAM_DE = (v) => (["panne", "retour", "decouverte", "incident_pris", "incident_clos"].includes(v) ? "coupures" : ["demande", "adossement_fait", "adossement_refuse", "accord", "declare_a_prouver", "prouve"].includes(v) ? "demandes" : "gestes");
  const ETATS_INC = { ouvert: ["incident ouvert", "dg"], depannage: ["dépannage en cours", "al"], retabli: ["rétabli · cause à noter", "ac"], resolu: ["résolu", "ok"] };
  const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  const QUI = { humain: "une personne", compte: "le compte", cassandra: "Cassandra", itare: "Itare", agent: "un agent", amizo: "Amizo" };
  const REGLAGES = ["echecs_avant_panne", "lent_ms", "proteges_en_ligne", "objectif_pct", "preuve_exigee", "delai_sonde_s", "retention_j"];
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
    ".si .barre input[data-note]{flex:1;min-width:180px}" +
    ".si .choix{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.si .choix>div{border:1px solid var(--line);border-radius:13px;padding:13px 14px;background:var(--surface);display:flex;flex-direction:column;gap:7px}.si .choix>div.pr{border-color:var(--accent)}.si .choix h4{margin:0}" +
    ".si .code{font:500 12.5px ui-monospace,'JetBrains Mono',Menlo,monospace;background:color-mix(in srgb,var(--txt) 6%,transparent);border-radius:9px;padding:9px 11px;overflow-wrap:anywhere;user-select:all}" +
    ".si .cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}.si .cal .ent{font:600 11px 'Inter',sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint);text-align:center}" +
    ".si .cal .j{min-height:76px;border:1px solid var(--line);border-top:3px solid var(--ok);border-radius:10px;background:var(--surface);padding:6px 7px;text-align:left;font:inherit;color:var(--txt);cursor:pointer;display:flex;flex-direction:column;gap:2px;overflow:hidden;min-width:0}" +
    ".si .cal .j.courte{border-top-color:var(--warn)}.si .cal .j.longue{border-top-color:var(--danger)}.si .cal .j.sans,.si .cal .j.futur{border-top-color:var(--line-strong,var(--line))}.si .cal .j.futur{opacity:.45;cursor:default}.si .cal .j.vide{border:0;background:none;cursor:default}" +
    ".si .cal .j.sel{outline:2px solid var(--accent);outline-offset:1px}.si .cal .j.auj b{color:var(--accent)}.si .cal .j b{font:650 13px 'Inter',sans-serif}.si .cal .j span{font-size:11px;color:var(--txt-soft);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
    ".si table.tab{width:100%;border-collapse:collapse;font-size:13px}.si table.tab th{text-align:left;font:600 11.5px 'Inter',sans-serif;color:var(--txt-faint);padding:6px 8px;border-bottom:1px solid var(--line)}.si table.tab td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}.si .defile{overflow-x:auto}" +
    ".si .regl{display:grid;gap:12px}.si .regl label{display:grid;gap:4px;font-size:13.5px}.si .regl label.coche{grid-template-columns:auto minmax(0,1fr);align-items:start;column-gap:10px}.si .regl input[type=number],.si .regl input[type=text]{max-width:160px}.si textarea{font:13.5px 'Inter',system-ui,sans-serif;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 11px;width:100%;min-height:64px}" +
    "@media (max-width:700px){.si .row,.si .row.c2,.si .row.c1{grid-template-columns:minmax(0,1fr)}.si .cote{align-items:flex-start;flex-direction:row;gap:10px}.si dl.g{grid-template-columns:110px minmax(0,1fr)}.si .nm b,.si .nm small{white-space:normal}.si .jl>div{grid-template-columns:auto minmax(0,1fr)}.si .jl>div>span:last-child{grid-column:1/-1}.si .jl>div>:nth-child(2){justify-self:start}" +
    ".si .choix{grid-template-columns:minmax(0,1fr)}.si .cal{gap:3px}.si .cal .j{min-height:46px;padding:4px}.si .cal .j span{display:none}.si .cal .j.ev b::after{content:' •';color:var(--accent)}}";

  // L'état de l'écran vit hors de la scène : le shell redessine l'onglet à chaque ouverture, et les autres écrans (Panorama, Hébergement) ouvrent un site d'ici.
  const S = { page: "vue", sel: null, onglet: "apercu", vue: null, lu: 0, q: "", filtre: "", p: 1, jours: 30, heures: 24 * 30, jfam: "", fiche: null, histo: null, copies: null, erreur: "",
    inc: null, soc: "", calSite: "", calMois: "", calJour: null };
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
  const portee = () => (S.vue && S.vue.portee) || {};
  const tenter = async (cap, args) => { try { return await agir(cap, args || {}); } catch (e) { return null; } };        // une lecture d'un autre module, qui peut manquer : on s'en passe sans le crier
  const court = (c) => String(c || "").split("@")[0];
  const jourMois = (ts) => { const d = new Date(ts * 1000); return d.getDate() + " " + MOIS[d.getMonth()]; };
  // Les sociétés : le superadministrateur d'une instance à plusieurs sociétés choisit celle qu'il regarde ; les autres ne voient de toute façon que la leur.
  const multi = () => !!(portee().multi && admin());
  const socNom = (id) => { const s = (portee().societes || []).find((x) => x.id === id); return s ? s.nom : id; };
  const visibles = (l) => (S.soc && portee().super ? (l || []).filter((s) => (s.societe || "-") === S.soc) : (l || []));
  const choixSoc = () => (portee().super && portee().multi ? '<select data-soc aria-label="Société"><option value="">toutes les sociétés</option>' + (portee().societes || []).map((x) => '<option value="' + esc(x.id) + '"' + (S.soc === x.id ? " selected" : "") + ">" + esc(x.nom) + "</option>").join("") + '<option value="-"' + (S.soc === "-" ? " selected" : "") + ">sans société</option></select>" : "");
  const pillInc = (i) => { const e = ETATS_INC[i.etat] || [i.etat, ""]; return K.pill(e[0], e[1]); };

  function etat(s) {
    if (s.preuve) return ["preuve en attente", "ac", 1];
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
    if (s.incident && s.incident.etat === "depannage") p.push(K.pill("dépannage · " + court(s.incident.pris_par), "al"));
    if (s.incident && s.incident.etat === "retabli") p.push(K.pill("incident à clore", "ac"));
    if (s.incident && s.incident.connu_jusqu) p.push(K.pill("panne connue", ""));
    if (multi()) p.push(K.pill(s.societe ? socNom(s.societe) + (s.societe_source === "compte" ? " · par son compte" : "") : "sans société", s.societe ? "" : "al"));
    return p.join("");
  }
  function incLigne(i) {
    const ouvert = i.etat !== "resolu";
    return '<button class="row" data-a="incident" data-id="' + i.id + '">' + pillInc(i) + '<span class="nm"><b class="mono">' + esc(i.domaine) + "</b><small>" + esc(ouvert ? i.diagnostic : (i.cause || "cause non notée")) + '</small></span><span class="note">' +
      (i.etat === "resolu" || i.etat === "retabli" ? "du " + esc(heure(i.debut)) + " au " + esc(heure(i.fin)) : "depuis " + esc(heure(i.debut)) + (i.pris_par ? " · " + esc(court(i.pris_par)) + " s’en occupe" : "")) + '</span><span class="cote"><span>' + esc(i.duree) + "</span><span>n° " + i.id + "</span></span></button>";
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
    else if (v.geste === "depanner" && v.incident) b = '<button class="btn mini pri" data-a="incident" data-id="' + v.incident + '">' + (v.niveau === "panne" ? "Dépanner ›" : "Clore ›") + "</button>";
    else if (v.geste === "prouver") b = '<button class="btn mini" data-a="site" data-d="' + esc(v.site) + '">Prouver ›</button>';
    else if (v.geste === "attribuer_societe") b = '<button class="btn mini" data-a="societe" data-d="' + esc(v.site) + '">Attribuer à une société…</button>';
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
      const l = visibles(v.sites), dans = new Set(l.map((s) => s.domaine)), vig = (v.vigilances || []).filter((x) => dans.has(x.site)), bas = l.filter((s) => s.up === false), graves = vig.filter((x) => x.niveau === "panne"), moy = vig.filter((x) => x.niveau === "regarder");
      const inc = l.filter((s) => s.incident && s.incident.etat !== "retabli").length, aclore = l.filter((s) => s.incident && s.incident.etat === "retabli").length;
      const m = graves.length ? "dg" : moy.length ? "al" : "";
      const titre = !l.length ? (v.portee.admin ? "Aucun site connu" : "Aucun site dans ta portée") : bas.length ? (bas.length === 1 ? "Un site ne répond pas : " + bas[0].domaine : bas.length + " sites ne répondent pas") : graves.length ? graves[0].titre : moy.length ? l.length + " site" + (l.length > 1 ? "s répondent" : " répond") + " · " + moy.length + " point" + (moy.length > 1 ? "s" : "") + " à regarder" : (l.length > 1 ? "Les " + l.length + " sites répondent" : "Le site répond");
      const sous = !l.length ? "« Déclarer un site » en ajoute un ; un administrateur peut aussi t’en attribuer." : (graves.length || moy.length) ? vig.filter((x) => x.niveau !== "info").slice(0, 2).map((x) => x.titre).join(" ; ") + "." : "Aucune panne, aucun certificat court.";
      const mes = l.filter((s) => s.dispo30), dm = mes.length ? mes.reduce((a, s) => a + s.dispo30.disponibilite, 0) / mes.length : null;
      const certs = l.filter((s) => typeof s.ssl_jours === "number"), cmin = certs.length ? Math.min.apply(null, certs.map((s) => s.ssl_jours)) : null;
      const dem = l.filter((s) => s.demande).length;
      const stat = (lib, val, note, cl, a, f) => '<button class="stat ' + (cl || "") + '" data-a="' + a + '"' + (f != null ? ' data-f="' + f + '"' : "") + ' style="cursor:pointer"><b>' + val + "</b><span>" + lib + '</span><span class="note">' + note + "</span></button>";
      const j = await lire("sites.journal", { limite: 10 });
      return entete(choixSoc() + '<button class="btn" data-a="recharger">Relire</button><button class="btn pri" data-a="declarer">Déclarer un site</button>') + bandeaux() +
        '<div class="carte"><div class="verdict"><div class="vm ' + m + '"></div><div><p class="vt">' + esc(titre) + '</p><p class="note">' + esc(sous) + "</p></div></div>" +
        '<div class="stats">' + stat("En ligne", l.filter((s) => s.up).length + " / " + l.filter((s) => s.up != null).length, bas.length ? bas.length + " en panne" : "tous répondent", bas.length ? "al" : "", "aller-sites", bas.length ? "tombes" : "") +
        stat("Disponibilité 30 j", pct(dm), mes.length + " site" + (mes.length > 1 ? "s" : "") + " mesuré" + (mes.length > 1 ? "s" : ""), "", "aller", "dispo") +
        stat("Certificats", cmin == null ? "—" : cmin < 0 ? "échu" : cmin + " j", cmin == null ? "pas encore lus" : "le plus court · Sécurité › Certificats", cmin != null && cmin < 21 ? "al" : "", "certificats") +
        stat("Incidents", inc, inc ? "à dépanner" : aclore ? aclore + " à clore" : "aucun ouvert", inc || aclore ? "al" : "", "aller", "incidents") +
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
      let l = visibles(v.sites).slice();
      const q = S.q.trim().toLowerCase(), F = { tombes: (s) => s.up === false, regarder: (s) => etat(s)[2] < 2, panneau: (s) => s.source === "panneau", declares: (s) => s.source !== "panneau", sans: (s) => !(s.comptes || []).length,
        sanssoc: (s) => s.societe_source !== "attribuee", aprouver: (s) => !!s.preuve };
      if (q) l = l.filter((s) => (s.domaine + " " + (s.comptes || []).join(" ") + " " + (s.proprietaire_panneau || "")).toLowerCase().includes(q));
      if (F[S.filtre]) l = l.filter(F[S.filtre]);
      l.sort((a, b) => etat(a)[2] - etat(b)[2] || ((a.dispo30 ? a.dispo30.disponibilite : 101) - (b.dispo30 ? b.dispo30.disponibilite : 101)) || a.domaine.localeCompare(b.domaine));
      const np = Math.max(1, Math.ceil(l.length / PAR)); S.p = Math.min(S.p, np);
      const page = l.slice((S.p - 1) * PAR, S.p * PAR);
      let corps;
      if (!l.length) corps = '<div class="vide"><b>Aucun site</b><p class="note">' + (v.sites.length ? "pour ce filtre." : "« Déclarer un site » en ajoute un.") + "</p></div>";
      else if (v.portee.admin) { const g = {}; page.forEach((s) => { const k = (s.comptes || []).join(", ") || (s.source === "panneau" ? "panneau · " + (s.proprietaire_panneau || "?") + " (sans compte Cassandra)" : "sans compte"); (g[k] = g[k] || []).push(s); }); corps = Object.keys(g).sort().map((k) => '<div class="grp">' + esc(k) + " · " + g[k].length + '</div><div class="rows">' + g[k].map(ligne).join("") + "</div>").join(""); }
      else corps = '<div class="rows">' + page.map(ligne).join("") + "</div>";
      const chips = [["", "tous"], ["tombes", "en panne"], ["regarder", "à regarder"], ["panneau", "du panneau"], ["declares", "déclarés"]].concat((v.sites || []).some((s) => s.preuve) ? [["aprouver", "à prouver"]] : [], v.portee.admin ? [["sans", "sans compte"]] : [], v.portee.super && v.portee.multi ? [["sanssoc", "non attribués à une société"]] : []);
      return entete(choixSoc() + '<button class="btn pri" data-a="declarer">Déclarer un site</button>') + bandeaux() +
        '<div class="carte"><div class="barre"><input type="search" data-q placeholder="Chercher un site' + (v.portee.admin ? ", un compte" : "") + '" aria-label="Chercher" value="' + esc(S.q) + '"></div>' +
        '<div class="chips">' + chips.map((c) => '<button class="chip" data-a="filtre" data-f="' + c[0] + '"' + (S.filtre === c[0] ? ' style="background:var(--accent);color:var(--on-accent,#fff);border-color:transparent"' : "") + ' aria-pressed="' + (S.filtre === c[0]) + '">' + c[1] + "</button>").join("") + "</div>" + corps +
        (l.length > PAR ? '<div class="pied-t"><span>' + ((S.p - 1) * PAR + 1) + "–" + Math.min(l.length, S.p * PAR) + " sur " + l.length + '</span><span class="acts"><button class="btn mini" data-a="page" data-p="' + (S.p - 1) + '"' + (S.p > 1 ? "" : " disabled") + '>‹ précédents</button><button class="btn mini" data-a="page" data-p="' + (S.p + 1) + '"' + (S.p < np ? "" : " disabled") + ">suivants ›</button></span></div>" : "") + "</div>";
    },

    async alertes() {
      const v = await chargerVue();
      if (!v) return entete() + bandeaux();
      const dans = new Set(visibles(v.sites).map((s) => s.domaine)), vig = (v.vigilances || []).filter((x) => dans.has(x.site)), j = await lire("sites.journal", { limite: 200 });
      const coup = ((j && j.lignes) || []).filter((x) => ["panne", "retour", "decouverte"].includes(x.verbe) && dans.has(x.domaine)).slice(0, 40);
      return entete(choixSoc()) + bandeaux() + '<div class="carte"><h3>' + vig.filter((x) => x.niveau !== "info").length + " alerte(s) · " + vig.filter((x) => x.niveau === "info").length + " pour information</h3>" + (vig.length ? '<div class="rows">' + vig.map(vigilance).join("") + "</div>" : '<p class="note"><b>Rien ne demande un geste.</b></p>') + "</div>" +
        '<div class="carte"><h3>Coupures et retours</h3>' + journalHtml(coup, true) + "</div>";
    },

    async dispo() {
      const v = await chargerVue(), d = await lire("sites.disponibilite", { jours: S.jours });
      const seg = choixSoc() + '<div class="seg" role="group" aria-label="Période">' + [7, 30, 90].map((n) => '<button class="' + (S.jours === n ? "on" : "") + '" data-a="jours" data-n="' + n + '">' + n + " jours</button>").join("") + "</div>";
      if (!d) return entete(seg) + bandeaux();
      const par = {}; visibles(v && v.sites).forEach((s) => { par[s.domaine] = s; });
      const l = (d.sites || []).filter((s) => par[s.domaine]).sort((a, b) => a.disponibilite - b.disponibilite);
      const cible = (s) => { const o = par[s.domaine].objectif, ec = Math.round((s.disponibilite - o) * 100) / 100; return [o, ec]; };
      return entete(seg) + bandeaux() + '<div class="carte">' + (l.length ? '<div class="rows">' + l.map((s) => { const c = cible(s); return '<button class="row" data-a="cal" data-d="' + esc(s.domaine) + '"><span class="vg' + (s.en_panne ? " dg" : "") + '">' + esc(initiales(s.domaine)) + '</span><span class="nm"><b class="mono">' + esc(s.domaine) + "</b><small>objectif " + pct(c[0]) + " · " + (c[1] >= 0 ? "tenu" : "manqué de " + pct(-c[1]).replace(" %", " pt")) + (s.en_panne ? " · en panne en ce moment" : "") + '</small></span><span class="note">' + s.pannes + " coupure" + (s.pannes > 1 ? "s" : "") + (s.indisponible_min ? " · " + esc(s.indisponible) + " indisponible" : "") + " · " + s.mesures + ' mesures</span><span class="cote"><span><b style="color:var(--' + (c[1] >= 0 ? "txt-strong,var(--txt)" : "danger") + ')">' + pct(s.disponibilite) + "</b></span><span>" + (s.reponse_moy_ms == null ? "—" : nb(s.reponse_moy_ms) + " ms en moyenne") + "</span></span></button>"; }).join("") + "</div>" : '<p class="note">' + esc(d.raison || "Aucune mesure.") + "</p>") +
        ((d.plus_suivis || []).length ? '<p class="note">Plus mesurés depuis deux jours, donc sans chiffre : ' + d.plus_suivis.map(esc).join(", ") + ".</p>" : "") + '<p class="note">Un clic ouvre le calendrier du site : ses coupures jour par jour, et son objectif.</p></div>' +
        '<div class="carte"><h4>Comment c’est compté</h4><p class="note">Une mesure toutes les 5 minutes. Une panne se dit après plusieurs échecs de suite et commence au premier ; une panne qui dure encore compte jusqu’à maintenant. Un site qu’on ne mesure plus n’a pas 100 % : il n’a pas de chiffre. L’objectif par défaut est de ' + pct(portee().objectif) + " ; chaque site peut avoir le sien, posé dans son calendrier.</p></div>";
    },

    async demandes() {
      const v = await chargerVue(), d = await lire("sites.demandes", { statut: "ouverte" });
      if (!v || !d) return entete() + bandeaux();
      const l = d.demandes || [], pr = d.preuves || [], ac = d.accords || [];
      return entete() + bandeaux() + '<div class="carte"><h3>Adossement au panneau</h3><p class="note">Un compte demande qu’un site déclaré passe au panneau.</p>' + (l.length ? l.map((x) => '<div class="alerte al"><div class="sp"><b class="mono">' + esc(x.domaine) + '</b><span class="note">demandé par ' + esc(x.compte) + " · " + esc(heure(x.ts)) + (x.message ? " · « " + esc(x.message) + " »" : "") + "</span></div>" +
        (v.portee.admin ? '<button class="btn mini pri" data-a="repondre" data-id="' + x.id + '" data-v="fait">Adossé, c’est fait</button><button class="btn mini" data-a="repondre" data-id="' + x.id + '" data-v="refusee">Refuser…</button>' : "") + '<button class="btn mini" data-a="site" data-d="' + esc(x.domaine) + '">La page du site</button></div>').join("") : '<p class="note">Aucune demande ouverte.</p>') + "</div>" +
        '<div class="carte"><h3>Preuves de propriété en attente</h3><p class="note">Le panneau dit à qui est un site ; hors de lui, c’est la preuve qui le dit. Tant qu’elle manque, le site n’est à personne et n’est pas mesuré.</p>' + (pr.length ? '<div class="rows">' + pr.map((x) => '<div class="row c2">' + K.pill("à prouver", "ac") + '<button class="nm" data-a="site" data-d="' + esc(x.domaine) + '" style="background:none;border:0;padding:0;text-align:left;color:inherit;font:inherit;cursor:pointer"><b class="mono">' + esc(x.domaine) + "</b><small>déclaré par " + esc(x.compte) + " · tombe le " + esc(jourMois(x.expire)) + (x.essais ? " · " + x.essais + " essai" + (x.essais > 1 ? "s" : "") : "") + '</small></button><span class="acts">' +
          (x.compte === moi() ? '<button class="btn mini pri" data-a="site" data-d="' + esc(x.domaine) + '">Prouver ›</button>' : "") + (v.portee.admin ? '<button class="btn mini" data-a="attester" data-d="' + esc(x.domaine) + '" data-c="' + esc(x.compte) + '">Attester</button>' : "") + "</span></div>").join("") + "</div>" : '<p class="note">Aucune.</p>') + "</div>" +
        '<div class="carte"><h3>Accords en cours</h3><p class="note">Un propriétaire autorise un geste lourd sur son site, pour un temps borné. L’accord tombe si le site change de compte.</p>' + (ac.length ? '<div class="rows">' + ac.map((x) => '<div class="row c2">' + K.pill(x.geste, "") + '<button class="nm" data-a="site" data-d="' + esc(x.domaine) + '" style="background:none;border:0;padding:0;text-align:left;color:inherit;font:inherit;cursor:pointer"><b class="mono">' + esc(x.domaine) + "</b><small>donné par " + esc(x.compte) + '</small></button><span class="note">jusqu’au ' + esc(heure(x.jusqu_a)) + "</span></div>").join("") + "</div>" : '<p class="note">Aucun accord en cours.</p>') + "</div>";
    },

    async incidents() {
      const v = await chargerVue(), r = await lire("sites.incidents", { jours: 30 });
      if (!r) return entete(choixSoc()) + bandeaux();
      const dans = new Set(visibles(v && v.sites).map((s) => s.domaine)), l = (r.incidents || []).filter((i) => !S.soc || dans.has(i.domaine)), o = l.filter((i) => i.etat !== "resolu"), f = l.filter((i) => i.etat === "resolu");
      return entete(choixSoc()) + bandeaux() +
        '<div class="carte"><h3>Ouverts</h3>' + (o.length ? '<div class="rows">' + o.map(incLigne).join("") + "</div>" : '<p class="note"><b>Aucun incident ouvert.</b> Un incident s’ouvre de lui-même quand une panne est confirmée.</p>') + "</div>" +
        '<div class="carte"><h3>Résolus sur 30 jours</h3><p class="note">Avec leur cause, pour ne pas la rechercher deux fois.</p>' + (f.length ? '<div class="rows">' + f.map(incLigne).join("") + "</div>" : '<p class="note">Aucun.</p>') + "</div>";
    },

    // ── un incident : ce qui se passe, que faire, qui a fait quoi ───────────────────────────────────────
    async incident() {
      await chargerVue();
      const i = await lire("sites.incident", { id: S.inc });
      const fil = '<p class="fil"><a data-a="aller" data-f="incidents">‹ tous les incidents</a></p>';
      if (!i) return fil + '<div class="carte vide"><b>Cet incident ne s’ouvre pas</b><p class="note">' + esc(S.erreur || "incident introuvable") + "</p></div>";
      const ouvert = i.etat === "ouvert" || i.etat === "depannage", d = esc(i.domaine), s = ((S.vue && S.vue.sites) || []).find((x) => x.domaine === i.domaine) || {}, panneau = s.source === "panneau";
      const contacts = (i.liens || []).filter((x) => x.genre === "contact").map((x) => x.ref);
      const tete = '<div class="carte"><div class="tete-s"><span class="vg gd' + (ouvert ? " dg" : "") + '">' + esc(initiales(i.domaine)) + '</span><div class="sp"><h1>' + d + '</h1><div class="pills">' + pillInc(i) + (i.connu_jusqu ? K.pill("panne connue jusqu’à " + heure(i.connu_jusqu), "") : "") + '</div><p class="note" style="margin-top:6px">Incident n° ' + i.id + " · " +
        (ouvert ? "depuis " + esc(i.duree) + " · début " + esc(heure(i.debut)) : "du " + esc(heure(i.debut)) + " au " + esc(heure(i.fin)) + " · " + esc(i.duree)) + (i.pris_par ? " · " + esc(i.pris_par === moi() ? "tu t’en occupes" : court(i.pris_par) + " s’en occupe") : "") + '</p></div><div class="acts"><button class="btn" data-a="site" data-d="' + d + '">La page du site</button><button class="btn" data-a="cal" data-d="' + d + '">Calendrier</button></div></div></div>';
      const mesures = (i.mesures || []).length ? '<div class="jl">' + i.mesures.map((m) => '<div><span class="t">' + esc(heure(m.ts)) + "</span>" + K.pill(m.up ? "répond" : "échec", m.up ? "ok" : "dg") + "<span>" + (m.code == null ? "sans réponse" : "HTTP " + m.code) + " · " + nb(m.ms || 0) + " ms" + (m.erreur ? " · " + esc(m.erreur) : "") + "</span></div>").join("") + "</div>" : '<p class="note">Pas de mesure récente.</p>';
      const quoi = i.etat === "resolu" ? "" : '<div class="carte"><h3>Ce qui se passe</h3><p style="font-size:15px;color:var(--txt-strong,var(--txt));margin:0">' + esc(i.en_ligne && !ouvert ? "Le site répond de nouveau. Il reste à noter ce qui s’est passé." : i.diagnostic) + "</p>" +
        ((i.tombes_aussi || []).length ? '<div class="bandeau al"><div class="sp"><b>' + i.tombes_aussi.length + " autre" + (i.tombes_aussi.length > 1 ? "s sites sont" : " site est") + " en panne en même temps</b> (" + i.tombes_aussi.slice(0, 4).map(esc).join(", ") + (i.tombes_aussi.length > 4 ? "…" : "") + ") : cherche d’abord une cause commune — la machine, le réseau, le DNS.</div></div>" : "") + "<h4>Les dernières mesures</h4>" + mesures + "</div>";
      const faire = !ouvert ? "" : '<div class="carte"><h3>Que faire</h3><p class="note">Dépanner, pas seulement accuser réception.</p><div class="choix">' +
        '<div class="pr"><h4>Demander à Cassandra de corriger</h4><p class="note">Elle lit le diagnostic, propose un plan et attend ton accord avant d’agir. Elle agit en ton nom, avec tes droits, jamais plus.</p><div class="acts"><button class="btn pri" data-a="cassandra" data-id="' + i.id + '">Demander un plan</button></div></div>' +
        '<div><h4>Dépanner moi-même</h4><p class="note">Dire que tu t’en occupes, puis vérifier après chaque geste.</p><div class="acts">' + (i.gestes.prendre ? '<button class="btn" data-a="prendre" data-id="' + i.id + '">' + (i.pris_par ? "Je prends la suite" : "Je m’en occupe") + "</button>" : "") + '<button class="btn" data-a="relever" data-d="' + d + '">Relever à nouveau</button>' + (panneau && admin() ? '<button class="btn" data-a="hebergement" data-d="' + d + '">Hébergement</button>' : "") + (panneau ? '<button class="btn" data-a="site" data-d="' + d + '" data-o="heberg">Copies de sauvegarde</button>' : "") + '<button class="btn" data-a="certificats">Certificats</button></div></div>' +
        '<div><h4>Confier à quelqu’un</h4><p class="note">' + (contacts.length ? "Contact rattaché au site : " + contacts.map(esc).join(", ") + "." : "Aucun contact rattaché à ce site (onglet Liens de sa page).") + '</p><div class="acts"><button class="btn" data-a="tache" data-id="' + i.id + '" data-d="' + d + '">Créer une tâche</button></div></div>' +
        '<div><h4>Le temps d’intervenir</h4><p class="note">' + (i.connu_jusqu ? "L’alerte de cette panne se tait jusqu’à " + esc(heure(i.connu_jusqu)) + ". Les mesures continuent." : "Dire que la panne est connue : son alerte se tait, l’incident reste ouvert, les mesures continuent.") + '</p><div class="acts">' + (i.connu_jusqu ? '<button class="btn" data-a="connu" data-id="' + i.id + '" data-h="0">Faire reparler l’alerte</button>' : '<button class="btn" data-a="connu" data-id="' + i.id + '" data-h="4">Connue, 4 h</button><button class="btn" data-a="connu" data-id="' + i.id + '" data-h="24">Connue, 24 h</button>') + "</div></div></div></div>";
      const clore = i.etat === "retabli" ? '<div class="carte"><h3>Clore</h3><label class="note" for="si-cause">La cause, pour la prochaine fois</label><textarea id="si-cause" data-cause placeholder="Ce qui s’est passé, ce qui l’a réglé…">' + esc(i.cause || "") + '</textarea><div class="acts"><button class="btn pri" data-a="clore" data-id="' + i.id + '">Clore l’incident</button></div></div>' :
        i.etat === "resolu" ? '<div class="carte"><h3>Cause</h3><p style="font-size:15px;color:var(--txt-strong,var(--txt));margin:0">' + esc(i.cause || "non notée") + '</p><p class="note">Clos par ' + esc(i.clos_par === "sonde" ? "la veille : le site est revenu seul" : court(i.clos_par)) + '.</p><textarea data-cause aria-label="Cause" placeholder="Noter ou corriger la cause…"></textarea><div class="acts"><button class="btn" data-a="clore" data-id="' + i.id + '">' + (i.cause ? "Corriger la cause" : "Noter la cause") + "</button></div></div>" :
        '<div class="carte"><h3>Clore</h3><p class="note">Un incident se clôt quand le site répond de nouveau. Tant qu’il ne répond pas, il reste ouvert.</p></div>';
      const chrono = '<div class="carte"><h3>Chronologie</h3><p class="note">Qui a su, qui a fait quoi.</p><div class="jl">' + (i.faits || []).map((x) => '<div><span class="t">' + esc(heure(x.ts)) + "</span>" + K.pill(x.acteur === "sonde" ? "la veille" : court(x.acteur), "") + "<span>" + esc(x.texte) + "</span></div>").join("") + '</div><div class="barre"><input type="text" data-note placeholder="Ajouter une note à la chronologie" aria-label="Note" autocomplete="off"><button class="btn" data-a="noter" data-id="' + i.id + '">Noter</button></div></div>';
      return fil + bandeaux() + tete + quoi + faire + '<div class="g2">' + chrono + clore + "</div>";
    },

    // ── le calendrier d'un site ─────────────────────────────────────────────────────────────────────────
    async calendrier() {
      const v = await chargerVue();
      if (!v) return entete() + bandeaux();
      const l = visibles(v.sites).filter((s) => !s.preuve);
      if (!l.length) return entete(choixSoc()) + bandeaux() + '<div class="carte vide"><b>Aucun site</b><p class="note">Le calendrier se remplit dès qu’un site est suivi.</p></div>';
      const s = l.find((x) => x.domaine === S.calSite) || l[0]; S.calSite = s.domaine;
      const auj = new Date(), moisCourant = auj.getFullYear() + "-" + z(auj.getMonth() + 1);
      if (!/^\d{4}-\d{2}$/.test(S.calMois)) S.calMois = moisCourant;
      const an = +S.calMois.slice(0, 4), mo = +S.calMois.slice(5), nj = new Date(an, mo, 0).getDate(), blancs = (new Date(an, mo - 1, 1).getDay() + 6) % 7;
      const moisDe = (k) => { const x = new Date(an, mo - 1 + k, 1); return x.getFullYear() + "-" + z(x.getMonth() + 1); };
      const c = await lire("sites.calendrier", { domaine: s.domaine, jours: Array.from({ length: nj + 1 }, (_, k) => new Date(an, mo - 1, k + 1).getTime() / 1000) });
      const choix = choixSoc() + '<select data-cal-site aria-label="Site">' + l.slice(0, 300).map((x) => '<option' + (x.domaine === s.domaine ? " selected" : "") + ">" + esc(x.domaine) + "</option>").join("") + "</select>";
      if (!c) return entete(choix) + bandeaux();
      const SYM = { incident: "⚑", retour: "✓", panne: "●", decouverte: "◎", geste: "✎" }, LIB = { ok: "sans coupure", courte: "coupure courte", longue: "coupure longue", sans: "pas de mesure", futur: "à venir" };
      const texte = (e) => (e.genre === "geste" ? (VERBES[e.texte] || e.texte) + (e.detail ? " · " + e.detail : "") : e.texte);
      const cases = c.jours.map((j, k) => { const n = k + 1, estAuj = S.calMois === moisCourant && n === auj.getDate(), ev = j.evenements.slice(0, 2).map((e) => "<span>" + SYM[e.genre] + " " + esc(texte(e)) + "</span>").join("") + (!j.evenements.length && j.rates ? "<span>● " + j.rates + " mesure" + (j.rates > 1 ? "s ratées" : " ratée") + "</span>" : "") + (j.evenements.length > 2 ? "<span>+ " + (j.evenements.length - 2) + "</span>" : "");
        return '<button class="j ' + j.etat + (estAuj ? " auj" : "") + (S.calJour === n ? " sel" : "") + (j.evenements.length || j.rates ? " ev" : "") + '" data-a="cal-jour" data-n="' + n + '"' + (j.etat === "futur" ? " disabled" : "") + ' aria-label="' + n + " " + MOIS[mo - 1] + " : " + LIB[j.etat] + (j.evenements.length ? ", " + j.evenements.length + " événement(s)" : "") + '"><b>' + n + "</b>" + ev + "</button>"; }).join("");
      const sel = S.calJour ? c.jours[S.calJour - 1] : null, m = c.mois;
      const detail = !sel ? '<p class="note">Clique un jour pour voir ce qui s’y est passé.</p>' : '<div class="bandeau in"><div class="sp"><b>' + S.calJour + " " + MOIS[mo - 1] + "</b> — " + LIB[sel.etat] + (sel.mesures ? " · " + pct(sel.disponibilite) + " sur " + sel.mesures + " mesures" + (sel.rates ? " · " + sel.rates + " ratée" + (sel.rates > 1 ? "s" : "") : "") + (sel.ms_max != null ? " · au pire " + nb(sel.ms_max) + " ms" : "") : "") + "</div></div>" +
        (sel.evenements.length ? '<div class="jl">' + sel.evenements.map((e) => '<div><span class="t">' + z(new Date(e.ts * 1000).getHours()) + ":" + z(new Date(e.ts * 1000).getMinutes()) + "</span>" + K.pill(e.genre === "geste" ? "geste" : e.genre === "incident" ? "incident" : VERBES[e.genre] || e.genre, e.genre === "incident" || e.genre === "panne" ? "dg" : e.genre === "retour" ? "ok" : "") + "<span>" + esc(texte(e)) + (e.acteur ? " · " + esc(court(e.acteur)) : "") + (e.incident ? ' · <a data-a="incident" data-id="' + e.incident + '" style="cursor:pointer;color:var(--accent)">ouvrir l’incident</a>' : "") + "</span></div>").join("") + "</div>" : sel.mesures && !sel.rates ? '<p class="note">Rien à signaler : le site a répondu toute la journée.</p>' : "");
      const ecart = m.disponibilite != null && m.avant != null ? Math.round((m.disponibilite - m.avant) * 100) / 100 : null;
      return entete(choix) + bandeaux() +
        '<div class="carte"><div class="barre" style="justify-content:space-between"><span class="acts"><button class="btn mini" data-a="cal-mois" data-m="' + moisDe(-1) + '" aria-label="Mois précédent">‹</button><b style="min-width:140px;text-align:center">' + MOIS[mo - 1] + " " + an + '</b><button class="btn mini" data-a="cal-mois" data-m="' + moisDe(1) + '" aria-label="Mois suivant"' + (S.calMois >= moisCourant ? " disabled" : "") + '>›</button></span><button class="btn mini" data-a="site" data-d="' + esc(s.domaine) + '">La page du site</button></div>' +
        '<div class="cal">' + ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"].map((x) => '<div class="ent">' + x + "</div>").join("") + '<div class="j vide"></div>'.repeat(blancs) + cases + "</div>" +
        '<div class="leg"><span><i style="background:var(--ok)"></i>sans coupure</span><span><i style="background:var(--warn)"></i>coupure courte</span><span><i style="background:var(--danger)"></i>coupure longue</span><span><i style="background:var(--line-strong,var(--line))"></i>pas de mesure</span><span>⚑ incident</span><span>✓ retour</span><span>✎ geste</span></div>' + detail + "</div>" +
        '<div class="carte"><h3>Le mois en chiffres</h3>' + (m.disponibilite == null ? '<p class="note"><b>Pas de mesure ce mois-là.</b> Les mesures se gardent ' + c.garde_j + " jours ; un mois sans mesure n’emprunte pas les chiffres d’un autre.</p>" :
          '<div class="stats"><div class="stat ' + (m.tenu ? "" : "al") + '"><b>' + pct(m.disponibilite) + '</b><span>disponibilité</span><span class="note">objectif ' + pct(m.objectif) + " · " + (m.tenu ? "tenu" : "manqué") + '</span></div><div class="stat"><b>' + pct(m.avant) + '</b><span>les ' + nj + ' jours d’avant</span><span class="note">' + (ecart == null ? "pas de mesure" : (ecart >= 0 ? "▲ +" : "▼ ") + ecart.toLocaleString("fr-FR") + " pt") + '</span></div><div class="stat ' + (m.jours_coupure ? "al" : "") + '"><b>' + m.jours_coupure + '</b><span>jours avec coupure</span><span class="note">sur ' + m.jours_mesures + " jour" + (m.jours_mesures > 1 ? "s mesurés" : " mesuré") + "</span></div><div class=\"stat\"><b>" + m.incidents + '</b><span>incidents</span><span class="note">pannes confirmées</span></div></div>') +
        '<div class="barre"><label class="note" for="si-obj">Objectif de ce site</label><input id="si-obj" type="text" inputmode="decimal" data-obj value="' + esc(String(s.objectif).replace(".", ",")) + '" style="max-width:90px" aria-label="Objectif en pourcentage"><span class="note">% de disponibilité' + (s.objectif_propre ? "" : " · celui du réglage") + '</span><button class="btn mini" data-a="objectif" data-d="' + esc(s.domaine) + '">Poser</button>' + (s.objectif_propre ? '<button class="btn mini" data-a="objectif" data-d="' + esc(s.domaine) + '" data-defaut="1">Rendre celui du réglage</button>' : "") + "</div></div>";
    },

    // ── les réglages : les seuils, et ce que chacun peut faire ─────────────────────────────────────────
    async reglages() {
      const v = await chargerVue();
      if (!v) return entete() + bandeaux();
      const g = await tenter("sites.gestes"), r = admin() ? await tenter("reglages.lire", { module: "sites" }) : null;
      const par = {}; ((r && r.reglages) || []).forEach((x) => { par[String(x.cle).replace(/^sites\./, "")] = x; });
      const champR = (k) => { const x = par[k]; if (!x) return ""; const val_ = x.valeur == null ? x.defaut : x.valeur;
        return x.type === "booleen" ? '<label class="coche"><input type="checkbox" data-regl="' + k + '"' + (val_ === true || /^(1|true|vrai|oui)$/i.test(String(val_)) ? " checked" : "") + "><span>" + esc(x.libelle) + "</span></label>" :
          "<label><span>" + esc(x.libelle) + '</span><input type="' + (x.type === "entier" ? "number" : "text") + '" data-regl="' + k + '" data-t="' + esc(x.type) + '" value="' + esc(val_ == null ? "" : val_) + '"></label>'; };
      const seuils = REGLAGES.map(champR).join("");
      const lignes = ((g && g.gestes) || []).map((x) => "<tr><td>" + esc(x.libelle) + "</td><td>" + esc(x.qui.map((q) => QUI[q] || q).join(", ")) + "</td><td>" + (x.qui.some((q) => q !== "humain" && q !== "compte") ? esc(x.paliers.join(" → ")) : "—") + "</td><td>" + esc(x.droit ? x.droit.replace(/^sites\./, "") : "—") + "</td></tr>").join("");
      return entete() + bandeaux() +
        (admin() ? '<div class="carte"><h3>Seuils et règles</h3>' + (seuils ? '<div class="regl">' + seuils + '</div><p class="note">Un réglage changé ici vaut tout de suite. Le seuil des certificats se règle dans Sécurité › Certificats : c’est lui qui fait foi.</p>' : '<p class="note">Les réglages de Sites se lisent dans Réglages ; ils ne sont pas lisibles d’ici pour ce compte.</p>') + "</div>" : "") +
        '<div class="carte"><h3>Ce que chacun peut faire sur ' + (admin() ? "les sites" : "tes sites") + '</h3><p class="note">Un agent agit toujours au nom d’un compte et n’a jamais plus de droits que lui. Au palier « raconter », il dit ce qu’il ferait et attend un accord ; à « auto », il le fait et en rend compte. Donner un accord de restauration reste réservé aux personnes.</p>' +
        (lignes ? '<div class="defile"><table class="tab"><thead><tr><th>Geste</th><th>Qui peut</th><th>Palier des agents</th><th>Droit exigé</th></tr></thead><tbody>' + lignes + "</tbody></table></div>" : '<p class="note">La liste des gestes n’est pas lisible pour l’instant.</p>') + "</div>" +
        '<div class="carte"><h3>Qui voit le menu Sites</h3><p class="note">Le menu n’apparaît que pour un compte concerné : il a un site (déclaré et prouvé, attribué, inscrit dans sa fiche, ou du panneau par son compte lié), il a une déclaration à prouver, ou il administre. Les autres ne voient pas un écran vide : ils ne voient pas l’entrée.</p>' +
        (multi() ? '<p class="note">Sociétés : un compte voit ses sites ; l’administrateur d’une société, ceux de sa société (attribués, ou par leur compte) ; le superadministrateur, ceux de toutes. Un site sans compte ni société n’est vu que du superadministrateur.</p>' : "") + "</div>";
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
      if (f.preuve && S.onglet !== "journal") S.onglet = "apercu";
      const acts = (f.gestes.relever ? '<button class="btn" data-a="relever" data-d="' + esc(d) + '">Relever maintenant</button>' : '<button class="btn" data-a="recharger">Relire</button>') + (f.preuve ? "" : '<button class="btn" data-a="cal" data-d="' + esc(d) + '">Calendrier</button>') +
        (f.gestes.demander ? '<button class="btn" data-a="demander" data-d="' + esc(d) + '">Demander l’adossement</button>' : "") + (f.gestes.transferer ? '<button class="btn" data-a="transferer" data-d="' + esc(d) + '">Transférer…</button>' : "") +
        (f.gestes.attribuer_societe ? '<button class="btn" data-a="societe" data-d="' + esc(d) + '">Société…</button>' : "") +
        (f.preuve && f.gestes.attribuer ? '<button class="btn" data-a="attester" data-d="' + esc(d) + '" data-c="' + esc(f.preuve.compte) + '">Attester</button>' : f.gestes.attribuer && !(s.comptes || []).length ? '<button class="btn" data-a="attribuer" data-d="' + esc(d) + '">Attribuer…</button>' : "") +
        (f.gestes.retirer ? '<button class="btn dng" data-a="retirer" data-d="' + esc(d) + '"' + (f.preuve ? ' data-preuve="1">Annuler la déclaration' : ">Retirer de la liste") + "</button>" : "");
      const tete = '<div class="carte"><div class="tete-s"><span class="vg gd' + (s.up === false ? " dg" : "") + '">' + esc(initiales(d)) + '</span><div class="sp"><h1>' + esc(d) + '</h1><div class="pills">' + pastilles(s) + '</div><p class="note" style="margin-top:6px">' + (f.preuve ? "Déclaré par" : "Propriétaire") + ' : <b>' + (f.mien ? "toi" : esc((s.comptes || []).join(", ") || "aucun compte Cassandra")) + "</b>" + (s.proprietaire_panneau ? " · compte « " + esc(s.proprietaire_panneau) + " » du panneau" : "") + '</p></div><div class="acts">' + acts + "</div></div>" +
        '<div class="onglets" role="tablist">' + ONGLETS.filter((o) => (o[0] !== "heberg" || !f.hors_panneau) && (!f.preuve || o[0] === "apercu" || o[0] === "journal")).map((o) => '<button role="tab" class="' + (S.onglet === o[0] ? "on" : "") + '" aria-selected="' + (S.onglet === o[0]) + '" data-a="onglet" data-o="' + o[0] + '">' + o[1] + "</button>").join("") + "</div>";
      return fil + bandeaux() + tete + (await O[S.onglet](f, s, e)) + "</div>";
    },
  };

  // ── les onglets de la page d'un site ────────────────────────────────────────────────────────────────
  const O = {
    async apercu(f, s) {
      const h = f.histoire || {}, d30 = s.dispo30, p = f.preuve, inc = s.incident;
      if (p) {
        // Une déclaration qui attend sa preuve : le site n'est encore à personne. Ce qu'il faut poser, et le bouton qui vérifie.
        return (f.mien ? "" : '<div class="bandeau in"><div class="sp">Déclaré par ' + esc(p.compte) + ", pas encore prouvé. Tu peux attester à sa place : le site lui est alors attribué.</div></div>") +
          '<div class="bandeau al"><div class="sp"><b>' + (f.mien ? "Prouve que ce site est à toi." : "Preuve de propriété en attente.") + "</b> Le panneau dit à qui est un site ; hors de lui, il faut une preuve. Tant qu’elle manque, le site n’est à personne : il n’est pas mesuré, et un autre compte peut encore le réclamer. La déclaration tombe le " + esc(jourMois(p.expire)) + ".</div></div>" +
          (p.dns ? "<h4>1. Par le DNS — un enregistrement TXT</h4><div class=\"code\">" + esc(p.dns.nom) + "   TXT   \"" + esc(p.dns.valeur) + '"</div><h4>2. Ou par un fichier — à déposer sur le site</h4><div class="code">' + esc(p.fichier.adresse) + "   →   " + esc(p.fichier.contenu) + '</div><p class="note">L’une des deux suffit. Un enregistrement DNS met parfois quelques minutes à paraître.</p>' : '<p class="note">Le jeton à poser n’est montré qu’au compte qui a déclaré le site.</p>') +
          (f.gestes.prouver ? '<div class="acts"><button class="btn pri" data-a="prouver" data-d="' + esc(f.domaine) + '">Vérifier maintenant</button></div>' : "");
      }
      return (inc && inc.etat !== "retabli" ? '<div class="bandeau da"><div class="sp"><b>Incident ouvert depuis ' + esc(inc.duree) + ".</b> " + esc(inc.diagnostic) + (inc.pris_par ? " " + esc(inc.pris_par === moi() ? "Tu t’en occupes." : court(inc.pris_par) + " s’en occupe.") : "") + '</div><button class="btn mini pri" data-a="incident" data-id="' + inc.id + '">Dépanner ›</button></div>' : "") +
        (inc && inc.etat === "retabli" ? '<div class="bandeau al"><div class="sp"><b>Le site répond de nouveau.</b> L’incident attend sa cause, pour ne pas la rechercher deux fois.</div><button class="btn mini pri" data-a="incident" data-id="' + inc.id + '">Clore ›</button></div>' : "") +
        (f.admin_autrui ? '<div class="bandeau in"><div class="sp">Ce site appartient à ' + esc((s.comptes || []).join(", ") || "un compte du panneau") + ". Tu vois son état, pas son contenu.</div></div>" : "") +
        (f.demande ? '<div class="bandeau al"><div class="sp"><b>Adossement demandé</b> par ' + esc(f.demande.compte) + (f.demande.message ? " : « " + esc(f.demande.message) + " »" : "") + ".</div>" + (admin() ? '<button class="btn mini pri" data-a="repondre" data-id="' + f.demande.id + '" data-v="fait">Adossé, c’est fait</button><button class="btn mini" data-a="repondre" data-id="' + f.demande.id + '" data-v="refusee">Refuser…</button>' : "") + "</div>" : "") +
        '<dl class="g"><dt>réponse</dt><dd>' + (s.up == null ? '<span class="note">pas encore relevé : dans moins de 5 minutes</span>' : (s.code == null ? "sans réponse" : s.code) + " en " + nb(s.ms || 0) + ' ms <span class="note">' + esc(heure(s.mesure)) + (s.erreur ? " · " + esc(s.erreur) : "") + "</span>") + "</dd>" +
        "<dt>disponibilité 30 j</dt><dd>" + (d30 ? pct(d30.disponibilite) + " · " + d30.pannes + " coupure" + (d30.pannes > 1 ? "s" : "") + (d30.indisponible_min ? " · " + esc(d30.indisponible) : "") : '<span class="note">pas encore de mesure</span>') + "</dd>" +
        "<dt>dernières 24 h</dt><dd>" + (h.mesures ? pct(h.disponibilite) + " · " + (h.reponse_moy_ms == null ? "—" : nb(h.reponse_moy_ms) + " ms en moyenne") + " · " + h.mesures + " mesures" : '<span class="note">pas encore de mesure</span>') + "</dd>" +
        "<dt>certificat</dt><dd>" + (typeof s.ssl_jours === "number" ? (s.ssl_jours < 0 ? "échu depuis " + (-s.ssl_jours) + " j" : "expire dans " + s.ssl_jours + " j") + ' <span class="note">' + esc({ certificats: "d’après Certificats", sonde: "lu par la sonde", panneau: "d’après le panneau" }[s.ssl_source] || "") + '</span> <button class="btn mini" data-a="certificats">Certificats</button>' : '<span class="note">pas encore lu</span>') + "</dd>" +
        "<dt>hébergement</dt><dd>" + (f.hors_panneau ? "hors panneau, déclaré à la main" : "panneau · compte « " + esc(s.proprietaire_panneau || "?") + " »" + (s.php ? " · PHP " + esc(s.php) : "")) + "</dd>" +
        "<dt>objectif</dt><dd>" + pct(s.objectif) + ' de disponibilité <span class="note">' + (s.objectif_propre ? "propre à ce site" : "celui du réglage") + (d30 ? " · sur 30 j : " + (d30.disponibilite >= s.objectif ? "tenu" : "manqué") : "") + '</span> <button class="btn mini" data-a="cal" data-d="' + esc(f.domaine) + '">Calendrier</button></dd>' +
        (multi() ? "<dt>société</dt><dd>" + (s.societe ? esc(socNom(s.societe)) + ' <span class="note">' + (s.societe_source === "attribuee" ? "attribuée au site" : "celle de son compte : le site lui-même n’est pas attribué") + "</span>" : '<span class="note">aucune : ni compte ni société, seuls les superadministrateurs le voient</span>') + (f.gestes.attribuer_societe ? ' <button class="btn mini" data-a="societe" data-d="' + esc(f.domaine) + '">Attribuer…</button>' : "") + "</dd>" : "") + "</dl>" +
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
        "<h4>Incidents</h4>" + ((f.incidents || []).length ? '<div class="rows">' + f.incidents.map(incLigne).join("") + "</div>" : '<p class="note">Aucun incident sur ce site.</p>') +
        '<div class="acts"><button class="btn mini" data-a="cal" data-d="' + esc(f.domaine) + '">Calendrier du site</button><button class="btn mini" data-a="courbes">Courbes détaillées (Historique)</button></div>';
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
      const preuve = portee().preuve_exigee && !admin();
      const m = await fenetre("Déclarer un site", champ("Nom du site", '<input type="text" data-n placeholder="mon-site.exemple.fr" autocomplete="off">', "Le nom nu : « www. », le protocole et le chemin sont retirés. Un site du panneau ne se déclare pas : il s’attribue." + (preuve ? " Il te sera ensuite demandé de prouver qu’il est à toi (un enregistrement DNS ou un fichier)." : "")), "Déclarer");
      if (!m) return; const r = await geste("sites.declarer", { domaine: val(m, "[data-n]") });
      if (r) { dire(r.preuve === "attente" ? "Site déclaré. Il reste à prouver qu’il est à toi." : "Site déclaré : la sonde le suit à son prochain tour.", "ok"); S.lu = 0; if (r.domaine) ouvrir(r.domaine); else rendre(); }
    },
    async retirer(b) {
      const att = b.dataset.preuve === "1";
      if (await K.confirmer((att ? "Annuler la déclaration de " : "Retirer ") + b.dataset.d, '<p class="note">' + (att ? "La déclaration en attente de preuve est retirée. Rien n’était encore mesuré." : "La sonde cesse de le suivre ; son historique reste. Ses rattachements sont mis de côté, ses accords tombent, sa demande ouverte se ferme.") + "</p>", att ? "Annuler la déclaration" : "Retirer", true) && await geste("sites.retirer", { domaine: b.dataset.d }, att ? "Déclaration retirée." : "Site retiré.")) { S.lu = 0; aller("sites"); }
    },
    // ── les gestes du lot 2 : la preuve, la société, l'objectif, la relève, les incidents, le calendrier, les réglages ──
    async prouver(b) { const r = await geste("sites.prouver", { domaine: b.dataset.d }); if (r) { dire("Preuve trouvée " + (r.par === "dns" ? "dans le DNS" : "dans le fichier") + " : " + b.dataset.d + " est à toi. La sonde le suit à son prochain tour.", "ok"); S.lu = 0; rendre(); } },
    async attester(b) { if (await K.confirmer("Attester " + b.dataset.d, '<p class="note">Tu attestes que ce site est bien à ' + esc(b.dataset.c) + " : il lui est attribué sans preuve, et la sonde le suit. Les autres déclarations de ce nom tombent.</p>", "Attester") && await geste("sites.attribuer", { domaine: b.dataset.d, compte: b.dataset.c }, "Site attribué à " + b.dataset.c + ".")) { S.lu = 0; rendre(); } },
    async societe(b) {
      const s = ((S.vue && S.vue.sites) || []).find((x) => x.domaine === b.dataset.d) || {}, attribuee = s.societe_source === "attribuee";
      const m = await fenetre("Société de " + b.dataset.d, champ("Société", '<select data-n>' + (portee().societes || []).map((x) => '<option value="' + esc(x.id) + '"' + (s.societe === x.id ? " selected" : "") + ">" + esc(x.nom) + "</option>").join("") + (attribuee ? '<option value="">aucune : celle de son compte</option>' : "") + "</select>", "Les administrateurs de cette société verront ce site, quel que soit son compte." + (s.societe && !attribuee ? " Aujourd’hui il suit celle de son compte (" + socNom(s.societe) + ")." : "")), "Attribuer");
      if (m && await geste("sites.attribuer_societe", { domaine: b.dataset.d, societe: val(m, "[data-n]") }, "Société attribuée.")) { S.lu = 0; rendre(); }
    },
    async objectif(b) {
      const defaut = b.dataset.defaut === "1", v = defaut ? "" : String((R.querySelector("[data-obj]") || {}).value || "").trim();
      if (!defaut && !v) return dire("Écris un pourcentage, de 90 à 100.", "err");
      if (await geste("sites.objectif", defaut ? { domaine: b.dataset.d } : { domaine: b.dataset.d, pct: v }, defaut ? "Objectif rendu au réglage." : "Objectif posé.")) { S.lu = 0; rendre(); }
    },
    async relever(b) { const r = await geste("sites.relever", { domaine: b.dataset.d }); if (r) { dire(b.dataset.d + " : " + (r.code == null ? "sans réponse" + (r.erreur ? " — " + r.erreur : "") : "HTTP " + r.code + " en " + nb(r.ms || 0) + " ms") + (r.recente ? " (mesuré il y a moins de trente secondes)" : ""), r.up ? "ok" : "err"); S.lu = 0; rendre(); } },
    incident: (b) => ouvrirInc(b.dataset.id),
    cal: (b) => { S.calSite = b.dataset.d; S.calJour = null; aller("calendrier"); },
    "cal-mois": (b) => { S.calMois = b.dataset.m; S.calJour = null; rendre(); },
    "cal-jour": (b) => { S.calJour = S.calJour === +b.dataset.n ? null : +b.dataset.n; rendre(); },
    async prendre(b) { if (await geste("sites.incident_prendre", { id: +b.dataset.id }, "Tu t’occupes de cet incident.")) { S.lu = 0; rendre(); } },
    async noter(b) { const t = String((R.querySelector("[data-note]") || {}).value || "").trim(); if (!t) return dire("Écris la note d’abord.", "err"); if (await geste("sites.incident_noter", { id: +b.dataset.id, texte: t })) rendre(); },
    async connu(b) { const h = +b.dataset.h; if (await geste("sites.incident_connu", { id: +b.dataset.id, heures: h }, h ? "Panne connue : son alerte se tait " + h + " h. L’incident reste ouvert." : "L’alerte de cette panne reparle.")) { S.lu = 0; rendre(); } },
    async clore(b) { const t = String((R.querySelector("[data-cause]") || {}).value || "").trim(); if (await geste("sites.incident_clore", { id: +b.dataset.id, cause: t }, "Cause notée. L’incident reste dans le calendrier du site.")) { S.lu = 0; rendre(); } },
    async tache(b) {
      const m = await fenetre("Créer une tâche", champ("La tâche", '<input type="text" data-n value="Dépanner ' + esc(b.dataset.d) + " (incident n° " + esc(b.dataset.id) + ')" autocomplete="off">') + champ("Pour qui (facultatif)", '<input type="text" data-r placeholder="nom@exemple.fr" autocomplete="off">', "Le compte à qui la confier ; vide : elle est à toi."), "Créer la tâche");
      if (!m) return; const a = { texte: val(m, "[data-n]"), notes: "Incident n° " + b.dataset.id + " du site " + b.dataset.d + "." }; if (val(m, "[data-r]")) a.responsable = val(m, "[data-r]");
      if (await geste("taches.creer", a, "Tâche créée.")) { await tenter("sites.incident_noter", { id: +b.dataset.id, texte: "Tâche créée : " + a.texte + (a.responsable ? " — confiée à " + a.responsable : "") }); rendre(); }
    },
    async cassandra(b) {
      const i = await tenter("sites.incident", { id: +b.dataset.id }); if (!i) return dire("Incident illisible.", "err");
      const t = "Le site " + i.domaine + " est en panne depuis " + i.duree + " (incident n° " + i.id + ") : " + i.diagnostic + " Lis l’incident (sites.incident), propose-moi un plan de dépannage étape par étape, et attends mon accord avant d’agir.";
      if (typeof window.d19Demander === "function" && await window.d19Demander(t)) dire("La demande est écrite dans la conversation : relis-la, puis envoie.", "ok"); else dire("La conversation n’est pas disponible ici.", "err");
    },
    async regler(t) {
      const k = t.dataset.regl, v = t.type === "checkbox" ? t.checked : t.dataset.t === "entier" ? Number(t.value) : String(t.value).trim();
      if (await geste("reglages.regler", { cle: "sites." + k, valeur: v }, "Réglage enregistré.")) { S.lu = 0; } else rendre();
    },
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
    R.innerHTML = html; dernier = { cle: cle(), html: html };
    if (foyer) { const n = R.querySelector("[data-q]"); if (n) { n.focus(); try { n.setSelectionRange(n.value.length, n.value.length); } catch (e) {} } }
  }
  const cle = () => [S.page, S.sel, S.onglet, S.inc, S.calSite, S.calMois, S.soc].join("|");
  const page_ = (p) => (P[p] && p !== "site" && p !== "incident" ? p : "vue");                       // une page du menu : jamais la page d'un site ou d'un incident, qui s'ouvrent par un clic
  function aller(page) { S.page = page_(page); S.sel = null; S.inc = null; S.p = 1; rendre(); const sc = R && R.closest(".tab-content"); if (sc && sc.scrollIntoView) window.scrollTo(0, 0); }
  function ouvrirInc(id) { S.page = "incident"; S.inc = +id || 0; S.sel = null; rendre(); window.scrollTo(0, 0); }
  function ouvrir(domaine, onglet) { S.page = "site"; S.sel = String(domaine || "").toLowerCase().replace(/^www\./, ""); S.onglet = ONGLETS.some((o) => o[0] === onglet) ? onglet : "apercu"; S.copies = null; rendre(); window.scrollTo(0, 0); }
  const actif = () => { const t = document.getElementById("tab-mysites"); return !!(t && t.classList.contains("active")); };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.sites = async function (corps) {
    K.injecter();
    if (!document.getElementById("si-css")) { const st = document.createElement("style"); st.id = "si-css"; st.textContent = CSS; document.head.appendChild(st); }
    const titre = corps.parentElement && corps.parentElement.querySelector(".sh-titre"); if (titre) titre.style.display = "none";      // chaque page a son propre titre
    corps.innerHTML = ""; R = document.createElement("div"); R.className = "kit si"; corps.appendChild(R);
    // Le shell redessine l'onglet à chaque retour sur l'écran : on remet tout de suite ce qu'on montrait, puis on relit. Sans cela la page clignotait sur « Lecture des sites… ».
    if (dernier && dernier.cle === cle() && !window.__stVue) R.innerHTML = dernier.html;
    R.addEventListener("click", (e) => { const b = e.target.closest("[data-a]"); if (!b || b.disabled) return; const f = A[b.dataset.a]; if (f) { e.preventDefault(); Promise.resolve(f(b)).catch((x) => dire(msg(x), "err")); } });
    R.addEventListener("input", (e) => { if (e.target.matches("[data-q]")) { S.q = e.target.value; S.p = 1; rendre(); } });
    R.addEventListener("change", (e) => { const t = e.target;
      if (t.matches("[data-soc]")) { S.soc = t.value; S.p = 1; S.calJour = null; rendre(); }
      else if (t.matches("[data-cal-site]")) { S.calSite = t.value; S.calJour = null; rendre(); }
      else if (t.matches("[data-regl]")) Promise.resolve(A.regler(t)).catch((x) => dire(msg(x), "err")); });
    R.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("[data-note]")) { const b = R.querySelector("[data-a=noter]"); if (b) b.click(); } });
    const v = window.__stVue; window.__stVue = null;
    if (v) { S.page = page_(v); S.sel = null; S.inc = null; }
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
