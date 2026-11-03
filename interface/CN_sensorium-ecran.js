// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Sensorium : l'écran (Maintenant, changements, capteurs, carte, démon, maintenance, comparer, alertes)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f4c478
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l'écran du module Sensorium à la ressemblance de docs/maquettes/CN_maquette-sensorium.html : une seule colonne de menu (celle de l'application), une recherche, des pages.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.sensorium) qui remplace l'onglet V18 ; tout vient des capacités sensorium.* (etat, demon, modules, fenetres, changements, historique, accepter, retirer_acceptation, fenetre_poser, fenetre_annuler, redemarrer) ; tout texte dynamique est échappé ; ce qui n'est pas encore branché le dit.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f4c478 ▼▼▼
/* La navigation est celle de la maquette validée : le menu vertical est celui de l'application (les vues du Sensorium en sont les sous-entrées), la page a une recherche et un
   bloc « Parcourir ». Aucune colonne de familles, aucune rangée de pilules. Règle : un chiffre affiché vient de sensorium.etat ; ce qui n'a pas de moteur garde la pastille « non branché ». */
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MONO = "ui-monospace,Menlo,Consolas,monospace";
  const VUES = [["maintenant", "Maintenant"], ["changements", "Ce qui a changé"], ["capteurs", "Les capteurs"], ["carte", "Carte de santé"], ["demon", "Le démon"],
                ["maintenance", "Maintenance"], ["comparer", "Comparer deux moments"], ["alertes", "Alertes et seuils"]];
  const CSS = ".sx{--e-verre:var(--surface);--e-filet:var(--line);--e-encre:var(--txt-strong);--e-encre2:var(--txt-soft);--e-encre3:var(--txt-muted);--e-doux:var(--ov-06);--e-ok:var(--ok);--e-al:var(--warn);--e-dg:var(--danger);" +
    "--e-okd:rgba(4,120,87,.11);--e-ald:rgba(180,83,9,.12);--e-dgd:rgba(190,18,60,.1);display:flex;flex-direction:column;gap:14px;color:var(--txt);font-size:13.5px;line-height:1.5;position:relative}" +
    ".sx *{box-sizing:border-box}.sx h1,.sx h2,.sx h3,.sx p{margin:0}.sx h1{font:600 19px/1.2 " + MONO + ";color:var(--e-encre)}.sx h2{font:600 12px/1.3 " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--e-encre2)}" +
    ".sx .verre{background:var(--e-verre);backdrop-filter:blur(18px) saturate(160%);-webkit-backdrop-filter:blur(18px) saturate(160%);border:1px solid var(--e-filet);border-radius:16px;box-shadow:var(--shadow-glass)}" +
    ".sx .mono{font-family:" + MONO + "}.sx .lib{font:600 10.5px/1.2 " + MONO + ";letter-spacing:.09em;text-transform:uppercase;color:var(--e-encre3)}.sx .note{font-size:11.5px;color:var(--e-encre3);line-height:1.5}.sx .vs{font-size:12.5px;color:var(--e-encre2)}" +
    ".sx .btn{border:1px solid var(--line-strong);background:var(--e-verre);color:var(--txt);border-radius:10px;padding:7px 12px;font:600 12px " + MONO + ";cursor:pointer;white-space:nowrap}.sx .btn:hover:not([disabled]){border-color:var(--accent)}" +
    ".sx .btn.prim{background:var(--accent);color:var(--on-accent);border-color:transparent}.sx .btn.dng{color:var(--e-dg);border-color:var(--e-dg)}.sx .btn[disabled]{opacity:.45;cursor:not-allowed}.sx .btn.pt{padding:4px 9px;font-size:11.5px;border-radius:8px}" +
    ".sx .puce{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 10.5px " + MONO + ";background:var(--e-doux);color:var(--accent);white-space:nowrap}" +
    ".sx .puce.ok{background:var(--e-okd);color:var(--e-ok)}.sx .puce.al{background:var(--e-ald);color:var(--e-al)}.sx .puce.dg{background:var(--e-dgd);color:var(--e-dg)}.sx .puce.mu{background:var(--e-doux);color:var(--e-encre3)}" +
    ".sx .nb{font:600 9.5px " + MONO + ";letter-spacing:.07em;text-transform:uppercase;border:1px dashed var(--e-filet);border-radius:99px;padding:2px 8px;color:var(--e-encre3);white-space:nowrap}" +
    ".sx .entete{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.sx .entete .d{display:flex;gap:8px;align-items:center;flex-wrap:wrap}" +
    ".sx .fil{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:12px;color:var(--e-encre3)}.sx .fil a{cursor:pointer;color:var(--accent)}.sx .fil b{color:var(--e-encre);font-weight:600}" +
    ".sx .rech{display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}.sx .cherche{position:relative;flex:1;min-width:240px;max-width:640px}" +
    ".sx .cherche input{width:100%;border:1px solid var(--line-strong);background:var(--e-verre);color:var(--txt);border-radius:12px;padding:10px 14px 10px 14px;font:13.5px inherit}" +
    ".sx .cres{position:absolute;left:0;right:0;top:calc(100% + 6px);background:var(--surface-solid,var(--e-verre));backdrop-filter:blur(22px);border:1px solid var(--line-strong);border-radius:14px;box-shadow:0 18px 50px rgba(16,24,40,.22);padding:6px;max-height:60vh;overflow:auto;z-index:40}" +
    ".sx .cres .gt{font:600 10px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--e-encre3);padding:8px 10px 3px}" +
    ".sx .cres button{display:flex;gap:10px;width:100%;border:0;background:transparent;color:var(--txt);border-radius:9px;padding:7px 10px;text-align:left;font:600 12.5px inherit;cursor:pointer}.sx .cres button:hover,.sx .cres button.sel{background:var(--e-doux)}" +
    ".sx .cres button .s{margin-left:auto;font:400 11.5px inherit;color:var(--e-encre3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:55%}.sx .cres button .s.w{color:var(--e-al)}" +
    ".sx .sec{padding:16px;display:flex;flex-direction:column;gap:12px;min-width:0}.sx .eb{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}" +
    ".sx .verdict{display:flex;gap:14px;align-items:flex-start}.sx .vmark{width:12px;height:12px;border-radius:50%;margin-top:7px;flex:none;background:var(--e-al);box-shadow:0 0 0 5px var(--e-ald)}" +
    ".sx .vmark.stable{background:var(--e-ok);box-shadow:0 0 0 5px var(--e-okd)}.sx .vmark.panne{background:var(--e-dg);box-shadow:0 0 0 5px var(--e-dgd)}.sx .vt{font:600 18px/1.25 " + MONO + ";color:var(--e-encre)}" +
    ".sx .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}.sx .kpi{border:1px solid var(--e-filet);border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:2px;background:var(--e-verre)}" +
    ".sx .kpi span{font:600 10px " + MONO + ";letter-spacing:.08em;text-transform:uppercase;color:var(--e-encre3)}.sx .kpi b{font:600 19px " + MONO + ";color:var(--e-encre)}.sx .kpi em{font-style:normal;font-size:11px;color:var(--e-encre3)}" +
    ".sx .rows{display:flex;flex-direction:column}.sx .row{display:flex;gap:10px;align-items:flex-start;padding:10px 4px;border-top:1px solid var(--e-filet)}.sx .row:first-child{border-top:0}" +
    ".sx .dot{width:8px;height:8px;border-radius:50%;background:var(--e-encre3);flex:none;display:inline-block;margin-top:7px}.sx .dot.ok{background:var(--e-ok)}.sx .dot.warn{background:var(--e-al)}.sx .dot.dg{background:var(--e-dg)}.sx .dot.mu{opacity:.5}" +
    ".sx .rt{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.sx .rt b{font-weight:600;font-size:13px}.sx .rt b.cl{cursor:pointer}.sx .rt b.cl:hover{color:var(--accent)}.sx .rt span{font-size:12.5px;color:var(--e-encre2)}.sx .rt .cause{color:var(--e-al)}" +
    ".sx .gest{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.sx .age{font:11px " + MONO + ";color:var(--e-encre3);white-space:nowrap}" +
    ".sx .cols2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:14px}.sx .carte{border:1px solid var(--e-filet);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:8px;background:var(--e-verre)}" +
    ".sx .chips{display:flex;gap:6px;flex-wrap:wrap}.sx .chip{border:1px solid var(--e-filet);background:transparent;color:var(--txt);border-radius:999px;padding:4px 11px;font:600 11.5px inherit;cursor:pointer}.sx .chip:hover{border-color:var(--accent)}.sx .chip.on{background:var(--e-doux);color:var(--accent);border-color:var(--accent)}" +
    ".sx .tuiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}.sx .tuile{border:1px solid var(--e-filet);border-radius:14px;background:var(--e-verre);color:var(--txt);padding:10px 12px;display:flex;flex-direction:column;gap:2px;text-align:left;cursor:pointer}" +
    ".sx .tuile:hover{border-color:var(--accent)}.sx .tuile.w{border-color:var(--e-al);background:var(--e-ald);grid-column:span 2}.sx .tuile .nm{font:600 12.5px inherit}.sx .tuile b{font:600 20px " + MONO + "}.sx .tuile.w b{color:var(--e-al)}" +
    ".sx .champ{display:flex;flex-direction:column;gap:4px}.sx .champ label{font:600 11px " + MONO + ";color:var(--e-encre2)}.sx .champ input,.sx .champ select,.sx .champ textarea{border:1px solid var(--line-strong);background:var(--e-verre);color:var(--txt);border-radius:10px;padding:8px 10px;font:13px inherit}" +
    ".sx .bandeau{display:flex;gap:10px;align-items:center;padding:9px 14px;border-radius:12px;background:var(--e-ald);color:var(--e-al);font:600 12.5px inherit}.sx .bandeau.dg{background:var(--e-dgd);color:var(--e-dg)}" +
    ".sx .bande{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--e-filet)}.sx .bande i{display:block;height:100%}.sx .bande i.ok{background:var(--e-okd)}.sx .bande i.al{background:var(--e-al)}" +
    ".sx .voile{position:fixed;inset:0;background:rgba(16,24,40,.36);display:flex;align-items:center;justify-content:center;padding:16px;z-index:9990}.sx .modal{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong);border-radius:18px;box-shadow:0 24px 70px rgba(16,24,40,.28);width:100%;max-width:520px;max-height:92vh;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:14px}" +
    ".sx .modal .act{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}.sx .err{color:var(--e-dg);font-size:12.5px}.sx .attente{display:flex;gap:10px;align-items:center;color:var(--e-encre2)}" +
    ".sx .attente i{width:16px;height:16px;border-radius:50%;border:2px solid var(--accent);border-top-color:transparent;animation:sxtourne .8s linear infinite}@keyframes sxtourne{to{transform:rotate(360deg)}}" +
    "@media (prefers-reduced-motion:reduce){.sx .attente i{animation:none}}@media (max-width:700px){.sx .tuile.w{grid-column:span 1}.sx .row{flex-wrap:wrap}.sx .gest{justify-content:flex-start}}";

  function css() { if (document.getElementById("sx-css")) return; const st = document.createElement("style"); st.id = "sx-css"; st.textContent = CSS; document.head.appendChild(st); }
  const agir = (c, a) => CASS.agir(c, a || {});
  // Les erreurs JavaScript de cet écran sont signalées au Sensorium (dédoublonnées côté serveur ; ici : au plus 5 par minute, jamais deux fois la même, et rien de réseau).
  // Posé dès le chargement du fichier, pas à l'ouverture de l'onglet : une erreur d'un autre écran se signale aussi.
  const SIGNALEES = {}; let fenetreErr = { t: 0, n: 0 };
  function signaler(message, source, ligne) {
    try {
      const m = String(message || "").slice(0, 300);
      if (!m || /ResizeObserver loop|^Failed to fetch|^NetworkError|^Load failed|^Script error\.?$/i.test(m)) return;
      const cle = m + "|" + source + "|" + ligne; if (SIGNALEES[cle]) return; SIGNALEES[cle] = 1;
      const t = Date.now(); if (t - fenetreErr.t > 60000) fenetreErr = { t: t, n: 0 }; if (++fenetreErr.n > 5) return;
      const p = CASS && CASS.agir && CASS.agir("sensorium.erreur_navigateur", { message: m, source: String(source || "").replace(location.origin, "").slice(0, 200), ligne: ligne || 0, page: String(location.hash || location.pathname).slice(0, 120) });
      if (p && p.catch) p.catch(() => {});
    } catch (e) { /* signaler une erreur ne doit jamais en faire une */ }
  }
  window.addEventListener("error", (e) => signaler(e.message, e.filename, e.lineno));
  window.addEventListener("unhandledrejection", (e) => { const r = e.reason; signaler("Promesse rejetée : " + ((r && r.message) || r), "", 0); });

  // ── l'état de l'écran ─────────────────────────────────────────────────────────
  const S = { vue: "maintenant", fam: null, obj: null, histo: null, dom: null, gen: null, etat: null, demon: null, modules: null, fen: null, comp: null, avant: "24h", filtre: "tous",
              modal: null, occupe: false, q: "", ouvrir: "", erreur: "" };
  let racine = null, timer = null;
  const rows = () => (S.etat && S.etat.rows) || [];
  const val = (k) => (rows().find((r) => r.wkey === k) || {}).value;
  const alerte = (r) => r.severity === "warning";
  const famLib = (id) => ((S.etat && S.etat.familles) || []).filter((f) => f[0] === id).map((f) => f[1])[0] || id;
  const domaines = () => (S.etat && S.etat.domaines) || [];
  const genres = () => (S.etat && S.etat.genres) || [];

  function age(ts) {
    if (!ts) return "?";
    let t = String(ts); if (!/[zZ]$|[+-]\d\d:?\d\d$/.test(t)) t = t.replace(" ", "T") + "Z";
    const d = new Date(t); if (isNaN(d)) return "?";
    const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    return s < 60 ? Math.round(s) + " s" : s < 3600 ? Math.round(s / 60) + " min" : s < 86400 ? Math.round(s / 3600) + " h" : Math.round(s / 86400) + " j";
  }
  const quand = (ts) => String(ts || "").slice(5, 16).replace("T", " ");
  function causes(r) { try { const d = r.detail ? JSON.parse(r.detail) : null; return (d && d.causes_probables) || []; } catch (e) { return []; } }
  const octets = (n) => { n = Number(n) || 0; return n < 1024 ? n + " o" : n < 1048576 ? (n / 1024).toFixed(1).replace(".", ",") + " Ko" : n < 1073741824 ? (n / 1048576).toFixed(1).replace(".", ",") + " Mo" : (n / 1073741824).toFixed(1).replace(".", ",") + " Go"; };
  const duree = (s) => { s = Math.max(0, Math.floor(Number(s) || 0)); const j = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return j ? j + " j " + h + " h" : h ? h + " h " + m + " min" : m ? m + " min" : s + " s"; };
  const objDe = (r) => r.objet ? r.objet.genre + "|" + r.objet.nom : "";

  // ── chargement ────────────────────────────────────────────────────────────────
  async function charger() {
    try { S.etat = await agir("sensorium.etat"); S.erreur = ""; } catch (e) { S.erreur = e.message || String(e); }
    try {
      if (S.vue === "demon") { S.demon = await agir("sensorium.demon").catch((e) => ({ muet: true, erreur: e.message })); S.modules = await agir("sensorium.modules").catch(() => null); }
      if (S.vue === "capteurs") S.erreursJs = await agir("sensorium.erreurs_navigateur").catch(() => null);
      if (S.vue === "maintenance" || S.vue === "alertes") S.fen = await agir("sensorium.fenetres").catch(() => null);
      if (S.vue === "comparer") await chargerComparaison();
    } catch (e) { /* une page qui n'a pas ses données le dit, elle ne tombe pas */ }
  }
  const DEPUIS = { "1h": 3600, "6h": 21600, "24h": 86400, "7j": 604800 };
  async function chargerComparaison() {
    const d = new Date(Date.now() - (DEPUIS[S.avant] || 86400) * 1000).toISOString().slice(0, 19);
    try { S.comp = { depuis: d, liste: await agir("sensorium.changements", { depuis: d }) }; } catch (e) { S.comp = { depuis: d, liste: [], erreur: e.message }; }
  }
  async function histoire(wkey) {
    let h = []; try { h = await agir("sensorium.historique", { cle: wkey }); } catch (e) { h = []; }
    S.histo = { wkey: wkey, lib: ((rows().find((r) => r.wkey === wkey) || {}).libelle) || wkey, liste: Array.isArray(h) ? h : (h && h.historique) || [] };
  }

  // ── la navigation ─────────────────────────────────────────────────────────────
  async function aller(v, garder) {
    if (!garder) { S.fam = S.obj = S.histo = null; S.dom = S.gen = null; }
    S.vue = v; S.q = ""; S.ouvrir = ""; S.modal = null;
    await charger(); dessiner();
  }
  window.sxAller = function (vue) { if (!vue) vue = "maintenant"; if (racine && document.body.contains(racine)) aller(vue); else window.__sxVue = vue; };

  // ── la recherche : vues, domaines, familles, objets, mesures ────────────────────
  function indexer() {
    const idx = [];
    VUES.forEach((v) => idx.push({ g: "Vues", lib: v[1], sub: "", go: "vue:" + v[0] }));
    domaines().forEach((d, i) => idx.push({ g: "Domaines", lib: d[1], sub: d[2].length + " familles", go: "dom:" + i }));
    const parFam = {}; rows().forEach((r) => { const f = parFam[r.famille] = parFam[r.famille] || { n: 0, w: 0 }; f.n++; if (alerte(r)) f.w++; });
    ((S.etat && S.etat.familles) || []).forEach((f) => { const c = parFam[f[0]]; if (c) idx.push({ g: "Familles", lib: f[1], sub: c.w ? c.w + " à regarder" : c.n + " relevés", w: c.w, go: "fam:" + f[0] }); });
    const vus = {}; rows().forEach((r) => { if (r.objet && !vus[objDe(r)]) { vus[objDe(r)] = { n: 0, w: 0, o: r.objet }; } if (r.objet) { vus[objDe(r)].n++; if (alerte(r)) vus[objDe(r)].w++; } });
    Object.keys(vus).forEach((k) => idx.push({ g: vus[k].o.genre, lib: vus[k].o.nom, sub: vus[k].w ? "à regarder" : "", w: vus[k].w, go: "obj:" + k }));
    rows().forEach((r) => idx.push({ g: "Mesures", lib: r.libelle || r.wkey, sub: String(r.value || ""), w: alerte(r) ? 1 : 0, go: "histo:" + r.wkey, cle: r.wkey }));
    return idx;
  }
  function resultats() {
    const idx = indexer(), q = S.q.trim().toLowerCase();
    let items;
    if (!q) items = idx.filter((x) => x.g === "Mesures" && x.w).slice(0, 7).map((x) => Object.assign({}, x, { g: "À regarder" }));
    else items = idx.filter((x) => (x.lib + " " + x.sub + " " + x.g + " " + (x.cle || "")).toLowerCase().indexOf(q) >= 0).slice(0, 14);
    return items;
  }
  function htmlRecherche() {
    let h = "";
    if (S.ouvrir === "fam") {
      const parFam = {}; rows().forEach((r) => { const f = parFam[r.famille] = parFam[r.famille] || { n: 0, w: 0 }; f.n++; if (alerte(r)) f.w++; });
      domaines().forEach((d) => {
        const fs = d[2].filter((f) => parFam[f]); if (!fs.length) return;
        const w = fs.reduce((a, f) => a + parFam[f].w, 0);
        h += '<div class="gt">' + esc(d[1]) + (w ? ' · <span style="color:var(--e-al)">' + w + " à regarder</span>" : "") + "</div>";
        fs.forEach((f) => { h += '<button data-a="fam:' + esc(f) + '"><span class="dot ' + (parFam[f].w ? "warn" : "ok") + '" style="margin:6px 8px 0 0"></span><span>' + esc(famLib(f)) + '</span><span class="s' + (parFam[f].w ? " w" : "") + '">' + (parFam[f].w ? parFam[f].w + " à regarder" : parFam[f].n + " relevés") + "</span></button>"; });
      });
    } else if (S.ouvrir === "q") {
      let g = "";
      resultats().forEach((x) => { if (x.g !== g) { g = x.g; h += '<div class="gt">' + esc(g) + "</div>"; } h += '<button data-a="' + esc(x.go) + '"><span>' + esc(x.lib) + '</span><span class="s' + (x.w ? " w" : "") + '">' + esc(x.sub) + "</span></button>"; });
      if (!h) h = '<div class="gt">Rien ne correspond</div>';
    }
    return h ? '<div class="cres" id="sx-res">' + h + "</div>" : "";
  }

  // ── les pièces ────────────────────────────────────────────────────────────────
  const kpi = (l, v, em) => v ? '<div class="kpi"><span>' + esc(l) + "</span><b>" + esc(v) + "</b>" + (em ? "<em>" + esc(em) + "</em>" : "") + "</div>" : "";
  function ligne(r, gestes) {
    const w = alerte(r), c = causes(r), a = r.acquit, m = r.maintenance;
    const boutons = w ? '<button class="btn pt" data-a="acc:' + esc(r.wkey) + '" title="Je sais, c\'est normal : se taire jusqu\'à l\'échéance (revient si ça empire)">Accepter…</button>'
      : a ? '<button class="btn pt" data-a="ret:' + esc(r.wkey) + '">Ne plus accepter</button>' : "";
    const reps = (r.gestes || []).map((x) => '<button class="btn pt" data-a="rep:' + esc(r.wkey) + "|" + esc(x.id) + '" title="Le geste passe par la commande root du courtier, se vérifie et s\'écrit au journal">' + esc(x.libelle) + "</button>").join("");
    return '<div class="row"><span class="dot ' + (w ? "warn" : a ? "mu" : "ok") + '"></span><div class="rt"><b class="cl" data-a="histo:' + esc(r.wkey) + '" title="' + esc(r.wkey) + ' — son histoire sur 30 jours">' + esc(r.libelle || r.wkey) +
      (a ? ' <span class="puce mu">acceptée</span>' : "") + (m ? ' <span class="puce al">en maintenance</span>' : "") + "</b><span>" + esc(r.value) + "</span>" +
      (a ? "<span>acceptée : " + esc(a.raison || "sans raison") + (a.jusqua ? " · jusqu'au " + esc(String(a.jusqua).slice(0, 10)) : "") + "</span>" : "") +
      (m ? "<span>maintenance jusqu'à " + esc(String(m.fin).slice(5, 16)) + (m.motif ? " : " + esc(m.motif) : "") + "</span>" : "") +
      (c.length ? '<span class="cause">cause probable : ' + esc(c[0]) + (c.length > 1 ? " (+" + (c.length - 1) + ")" : "") + "</span>" : "") +
      '</div><div class="gest"><span class="age" title="' + esc(r.observed_at || "") + '">il y a ' + age(r.observed_at) + "</span>" + reps + boutons + "</div></div>";
  }
  const liste = (rs) => rs.length ? '<div class="rows">' + rs.map(ligne).join("") + "</div>" : '<div class="note">Rien à montrer ici.</div>';
  const section = (titre, corps, droite) => '<section class="verre sec"><div class="eb"><h2>' + titre + "</h2>" + (droite || "") + "</div>" + corps + "</section>";
  const puceNB = '<span class="nb">non branché</span>';

  // ── les pages ─────────────────────────────────────────────────────────────────
  function pMaintenant() {
    const al = rows().filter((r) => alerte(r) && r.famille !== "capteur"), capKO = rows().filter((r) => alerte(r) && r.famille === "capteur");
    const sante = String(val("health.score") || ""), i = sante.indexOf(" · ");
    const titre = al.length ? al.length + " point" + (al.length > 1 ? "s" : "") + " demande" + (al.length > 1 ? "nt" : "") + " un regard" : "Tout ce qui est mesuré va bien";
    const prev = rows().filter((r) => r.wkey.indexOf("prevision.") === 0);
    const flotte = rows().filter((r) => r.wkey.indexOf("fleet.") === 0);
    const hist = (S.etat.changes || []).filter((c) => Date.now() - new Date(String(c.ts).replace(" ", "T") + (/Z$/.test(c.ts) ? "" : "Z")).getTime() < 86400000);
    return '<section class="verre sec"><div class="verdict"><span class="vmark ' + (al.length ? "" : "stable") + '"></span><div><p class="vt">' + esc(titre) + '</p><p class="vs">' +
      esc(val("system.hostname") || S.etat.hote || "") + " · " + esc(val("system.os") || "") + " · allumée depuis " + esc(val("system.uptime") || "?") + " · " + rows().length + " relevés" +
      (capKO.length ? ' · <a style="color:var(--e-al);cursor:pointer" data-a="vue:capteurs">' + capKO.length + " capteur" + (capKO.length > 1 ? "s" : "") + " en défaut</a>" : "") + "</p></div></div>" +
      '<div class="kpis">' + kpi("Santé", i > 0 ? sante.slice(0, i) : sante, i > 0 ? sante.slice(i + 3) : "") + kpi("Disque /", val("disk./.usage")) + kpi("RAM", val("ram.usage")) +
      kpi("Charge", val("load.1m"), val("cpu.load") ? "CPU " + val("cpu.load") : "") + kpi("Température", val("system.temperature")) + kpi("Mises à jour", String(val("maj.paquets") || "").split(",")[0]) + "</div></section>" +
      (hist.length ? section("Les 24 dernières heures", '<div class="note">' + hist.length + " changement" + (hist.length > 1 ? "s" : "") + " : " + hist.slice(0, 4).map((c) => esc(c.entity_name)).join(", ") + (hist.length > 4 ? "…" : "") +
        ' <a style="color:var(--accent);cursor:pointer" data-a="vue:changements">tout voir</a></div>') : "") +
      (al.length ? section("Ce qui demande un regard", liste(al)) : "") + (prev.length ? section("Ce qui va arriver", liste(prev)) : "") +
      section("La flotte", flotte.length ? '<div class="rows">' + flotte.map((r) => { const m = r.wkey.slice(6), det = rows().filter((x) => x.wkey.indexOf("machine." + m + ".") === 0 && !/\.sonde$/.test(x.wkey));
        const w = alerte(r) || det.some(alerte); return '<div class="row"><span class="dot ' + (w ? "warn" : "ok") + '"></span><div class="rt"><b class="cl" data-a="obj:Machines|' + esc(m) + '">' + esc(m) + "</b><span>" + esc(r.value) +
          (det.length ? " · " + det.slice(0, 4).map((x) => esc(x.libelle.replace(/^[^—]*— /, "")) + " " + esc(x.value)).join(" · ") : "") + '</span></div><span class="age">il y a ' + age(r.observed_at) + "</span></div>"; }).join("") + "</div>" : '<div class="note">Aucune machine relevée.</div>',
        '<button class="btn pt" data-a="relever">Relever la flotte</button>') + pParcourir();
  }
  function pParcourir() {
    const parFam = {}; rows().forEach((r) => { if (alerte(r)) parFam[r.famille] = (parFam[r.famille] || 0) + 1; });
    const dom = domaines().map((d, i) => { const w = d[2].reduce((a, f) => a + (parFam[f] || 0), 0); return '<button class="chip" data-a="dom:' + i + '">' + esc(d[1]) + (w ? ' <b style="color:var(--e-al)">' + w + " ⚠</b>" : "") + "</button>"; }).join("");
    const parGen = {}; rows().forEach((r) => { if (r.objet) { const g = parGen[r.objet.genre] = parGen[r.objet.genre] || { w: new Set(), n: new Set() }; g.n.add(r.objet.nom); if (alerte(r)) g.w.add(r.objet.nom); } });
    const gen = genres().filter((g) => parGen[g]).map((g, i) => '<button class="chip" data-a="gen:' + esc(g) + '">' + esc(g) + (parGen[g].w.size ? ' <b style="color:var(--e-al)">' + parGen[g].w.size + " ⚠</b>" : "") + "</button>").join("");
    return section("Parcourir", '<div class="cols2"><div class="carte"><span class="lib">Par domaine</span><div class="chips">' + dom + '</div></div><div class="carte"><span class="lib">Par objet</span><div class="chips">' + gen + "</div></div></div>",
      '<span class="note">ou cherche en haut : un site, une machine, une mesure</span>');
  }
  function pChangements() {
    const co = S.etat.correlations || [], ch = (S.etat.changes || []).filter((c) => S.filtre === "tous" || c.severity === "warning");
    const mot = { added: "apparu", removed: "disparu", modified: "changé" };
    return (co.length ? section("Alertes et leur cause probable", '<div class="rows">' + co.map((c) => { let cs = []; try { cs = JSON.parse(c.causes || "[]"); } catch (e) { cs = []; }
        const r = rows().find((x) => x.wkey === c.entite); return '<div class="row"><span class="dot warn"></span><div class="rt"><b>' + esc(r ? r.libelle : c.entite) + "</b><span>" + esc(c.alerte) + "</span>" + cs.map((x) => "<span>↳ " + esc(x) + "</span>").join("") +
          '</div><span class="age">' + esc(quand(c.ts)) + "</span></div>"; }).join("") + "</div>") : "") +
      section("Derniers changements", (ch.length ? '<div class="rows">' + ch.map((c) => '<div class="row"><span class="dot ' + (c.severity === "warning" ? "warn" : "ok") + '"></span><div class="rt"><b>' + esc(c.entity_name) + ' <span class="puce mu">' + esc(mot[c.change_type] || c.change_type) + "</span></b><span>" + esc(c.new_value || c.old_value || "") + "</span>" +
        (c.old_value && c.new_value ? '<span class="age">avant : ' + esc(c.old_value) + "</span>" : "") + '</div><span class="age">' + esc(quand(c.ts)) + "</span></div>").join("") + "</div>" : '<div class="note">Aucun changement relevé.</div>'),
        '<div class="chips"><button class="chip' + (S.filtre === "tous" ? " on" : "") + '" data-a="filtre:tous">Tous</button><button class="chip' + (S.filtre === "warn" ? " on" : "") + '" data-a="filtre:warn">Seulement ceux qui alertent</button></div>') +
      '<div class="note">Le journal du collecteur garde 180 jours ; les derniers changements se lisent ici, le reste dans « Comparer deux moments ».</div>';
  }
  function pCapteurs() {
    const cap = rows().filter((r) => r.famille === "capteur"), ko = cap.filter(alerte).length;
    return section("Les capteurs eux-mêmes · " + ko + " en défaut", '<p class="vs">Un capteur en panne ou muet ne mesure plus : ce qu\'il avait relevé vieillit sans le dire. On le dit ici.</p>' +
      (cap.length ? liste(cap) : '<div class="note">Pas encore de santé des capteurs (premier cycle en cours).</div>')) + pErreursJs();
  }
  function pErreursJs() {
    const l = (S.erreursJs && S.erreursJs.erreurs) || [];
    return section("Erreurs JavaScript des écrans · " + l.length, '<p class="vs">Ce que les écrans des utilisateurs ont signalé : un message, un fichier, une ligne. Trois erreurs distinctes dans l\'heure ouvrent un constat.</p>' +
      (l.length ? '<div class="rows">' + l.map((e) => '<div class="row"><span class="dot warn"></span><div class="rt"><b>' + esc(e.message) + '</b><span>' + esc(e.source || "?") + (e.ligne ? ":" + e.ligne : "") + " · " + esc(e.page || "") +
        "</span></div><span class=\"age\">" + (e.n > 1 ? e.n + " fois · " : "") + esc(quand(e.derniere)) + "</span></div>").join("") + "</div>" : '<div class="note">Aucune erreur signalée.</div>'));
  }
  function tuilesFam(ids) {
    const parFam = {}; rows().forEach((r) => { const f = parFam[r.famille] = parFam[r.famille] || { n: 0, w: 0 }; f.n++; if (alerte(r)) f.w++; });
    return '<div class="tuiles">' + ids.filter((f) => parFam[f]).map((f) => '<button class="tuile' + (parFam[f].w ? " w" : "") + '" data-a="fam:' + esc(f) + '"><span class="nm">' + esc(famLib(f)) + "</span><b>" + (parFam[f].w ? parFam[f].w + " ⚠" : parFam[f].n) + '</b><span class="note">' + (parFam[f].w ? "à regarder" : "relevés") + "</span></button>").join("") + "</div>";
  }
  function pCarte() { return section("Carte de santé", domaines().map((d) => '<div><div class="lib" style="margin:8px 0">' + esc(d[1]) + "</div>" + tuilesFam(d[2]) + "</div>").join(""), '<span class="note">une case par famille : elle s\'élargit quand elle alerte</span>'); }
  function pDomaine() { const d = domaines()[S.dom]; return d ? section(esc(d[1]), tuilesFam(d[2]), '<span class="note">' + d[2].length + " familles de capteurs</span>") : ""; }
  function pFamille() {
    const rs = rows().filter((r) => r.famille === S.fam).sort((a, b) => alerte(b) - alerte(a) || String(a.wkey).localeCompare(b.wkey));
    const f = S.filtre === "warn" ? rs.filter(alerte) : S.filtre === "acc" ? rs.filter((r) => r.acquit) : rs;
    return section(esc(famLib(S.fam)) + " · " + rs.length + " relevé" + (rs.length > 1 ? "s" : ""), liste(f),
      '<div class="chips"><button class="chip' + (S.filtre === "tous" ? " on" : "") + '" data-a="filtre:tous">Tous</button><button class="chip' + (S.filtre === "warn" ? " on" : "") + '" data-a="filtre:warn">À regarder</button><button class="chip' + (S.filtre === "acc" ? " on" : "") + '" data-a="filtre:acc">Acceptés</button></div>');
  }
  function pGenre() {
    const noms = {}; rows().forEach((r) => { if (r.objet && r.objet.genre === S.gen) { const o = noms[r.objet.nom] = noms[r.objet.nom] || { n: 0, w: 0 }; o.n++; if (alerte(r)) o.w++; } });
    const ks = Object.keys(noms).sort((a, b) => noms[b].w - noms[a].w || a.localeCompare(b));
    return section(esc(S.gen), ks.length ? '<div class="rows">' + ks.map((k) => '<div class="row"><span class="dot ' + (noms[k].w ? "warn" : "ok") + '"></span><div class="rt"><b class="cl" data-a="obj:' + esc(S.gen) + "|" + esc(k) + '">' + esc(k) + "</b><span>" + (noms[k].w ? noms[k].w + " à regarder · " : "") + noms[k].n + " relevés</span></div>" +
      '<div class="gest"><button class="btn pt" data-a="obj:' + esc(S.gen) + "|" + esc(k) + '">Ouvrir la fiche</button></div></div>').join("") + "</div>" : '<div class="note">Aucun objet de ce genre.</div>', '<span class="note">un clic ouvre la fiche de l\'objet</span>');
  }
  function pObjet() {
    const [genre, nom] = S.obj.split("|"), rs = rows().filter((r) => r.objet && r.objet.genre === genre && r.objet.nom === nom), w = rs.some(alerte);
    const parFam = {}; rs.forEach((r) => (parFam[r.famille] = parFam[r.famille] || []).push(r));
    return '<section class="verre sec"><div class="eb"><span class="lib">' + esc(genre) + " › " + esc(nom) + "</span></div><div class=\"verdict\"><span class=\"vmark " + (w ? "" : "stable") + '"></span><div><p class="vt">' + esc(nom) + " — " + (w ? "demande un regard" : "tout va bien") +
      '</p><p class="vs">' + rs.length + " relevé" + (rs.length > 1 ? "s" : "") + " dans " + Object.keys(parFam).length + " famille" + (Object.keys(parFam).length > 1 ? "s" : "") + " de capteurs, réunis ici : on regarde l'objet, pas le capteur.</p></div></div>" +
      '<div class="chips">' + Object.keys(parFam).map((f) => '<button class="chip" data-a="fam:' + esc(f) + '" title="Ouvrir toute la famille">' + esc(famLib(f)) + " ›</button>").join("") + "</div></section>" +
      Object.keys(parFam).map((f) => section(esc(famLib(f)), liste(parFam[f]))).join("") + (rs.length ? "" : section("Rien", '<div class="note">Plus aucune mesure ne parle de cet objet.</div>'));
  }
  function pHistoire() {
    const h = S.histo, cur = rows().find((r) => r.wkey === h.wkey) || {}, liste_ = h.liste.slice().sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
    const fin = Date.now(), debut = fin - 30 * 86400000, T = (ts) => new Date(String(ts).replace(" ", "T") + (/Z$|[+-]\d\d:?\d\d$/.test(String(ts)) ? "" : "Z")).getTime();
    let etat = "info", t = debut, alerteMs = 0; const segs = [];
    liste_.forEach((c) => { const q = Math.max(T(c.ts), debut); if (!isNaN(q) && q > t) { segs.push([etat, q - t]); if (etat === "warning") alerteMs += q - t; t = q; } etat = c.severity || "info"; });
    if (fin > t) { segs.push([alerte(cur) ? "warning" : etat, fin - t]); if (alerte(cur) || etat === "warning") alerteMs += fin - t; }
    const dispo = (100 * (1 - alerteMs / (fin - debut))).toFixed(1).replace(".", ",");
    const mot = { added: "apparue", removed: "disparue", modified: "a changé" };
    return '<section class="verre sec"><div class="eb"><span class="lib"><a style="cursor:pointer;color:var(--accent)" data-a="retour">← retour</a> · ' + esc(h.lib) + '</span></div><div class="verdict"><span class="vmark ' + (alerte(cur) ? "" : "stable") + '"></span><div><p class="vt">' + esc(cur.value || "—") +
      '</p><p class="vs">Disponibilité sur 30 jours : <b>' + dispo + " %</b> · " + liste_.length + " changement" + (liste_.length > 1 ? "s" : "") + " en 30 jours</p></div></div>" +
      '<div class="bande" title="30 jours : vert = sans alerte, orange = en alerte">' + segs.map((s) => '<i class="' + (s[0] === "warning" ? "al" : "ok") + '" style="width:' + (100 * s[1] / (fin - debut)).toFixed(2) + '%"></i>').join("") + "</div>" +
      '<div class="note">Il y a 30 jours ← → maintenant. Les trous de mesure ne sont pas reliés : une bande ne dit que ce que le collecteur a vu changer.</div></section>' +
      section("Son histoire", liste_.length ? '<div class="rows">' + liste_.slice().reverse().slice(0, 60).map((c) => '<div class="row"><span class="dot ' + (c.severity === "warning" ? "warn" : "ok") + '"></span><div class="rt"><b>' + esc(mot[c.change_type] || c.change_type) + "</b><span>" + esc(c.new_value || c.old_value || "") + "</span>" +
        (c.old_value && c.new_value ? '<span class="age">avant : ' + esc(c.old_value) + "</span>" : "") + '</div><span class="age">' + esc(quand(c.ts)) + "</span></div>").join("") + "</div>" : '<div class="note">Rien n\'a changé en 30 jours.</div>');
  }
  function pDemon() {
    const d = S.demon, mods = S.modules;
    const cass = rows().filter((r) => /^(noyau|module_noyau|store|code|courtier)\./.test(r.wkey));
    let haut;
    if (!d) haut = '<div class="note">Lecture du démon…</div>';
    else if (d.muet) haut = '<div class="verdict"><span class="vmark panne"></span><div><p class="vt">Le démon ne répond pas</p><p class="vs">' + esc(d.erreur || "") + " · socket " + esc(d.socket || "") + "</p></div></div>";
    else if (d.ancien) haut = '<div class="verdict"><span class="vmark"></span><div><p class="vt">Le démon répond, mais ne sait pas encore dire son état</p><p class="vs">C\'est un démon d\'avant cette page : un redémarrage le remplace par la version déployée.</p></div></div>';
    else haut = '<div class="verdict"><span class="vmark stable"></span><div><p class="vt">Il tourne, il bat, il répond</p><p class="vs">version ' + esc(d.version) + " · démarré il y a " + esc(duree(d.duree_s)) + (d.watchdog_s ? " · limite du watchdog " + d.watchdog_s + " s" : "") + '</p></div></div><div class="kpis">' +
      kpi("Battement", d.battement_il_y_a_s != null ? "il y a " + d.battement_il_y_a_s + " s" : "—", d.watchdog_s ? "limite : " + d.watchdog_s + " s" : "") + kpi("Processus", String(d.pid), d.rss_mo ? d.rss_mo + " Mo de RAM" : "") + kpi("Base", octets(d.base_octets), "conservée " + d.retention_jours + " j") +
      kpi("Passe rapide", d.passes && d.passes.rapide.n ? d.passes.rapide.duree + " s" : "—", d.passes && d.passes.rapide.il_y_a_s != null ? "il y a " + d.passes.rapide.il_y_a_s + " s" : "") +
      kpi("Passe complète", d.passes && d.passes.complete.n ? d.passes.complete.duree + " s" : "—", d.passes && d.passes.complete.il_y_a_s != null ? "il y a " + d.passes.complete.il_y_a_s + " s" : "") + "</div>";
    const hist = (d && d.redemarrages) || [];
    const sante = mods && !mods.muet ? Object.keys(mods.modules || {}).filter((k) => mods.modules[k].verdict !== "sain").sort() : [];
    return '<section class="verre sec"><div class="eb"><h2>Le démon du Sensorium</h2><div class="gest"><button class="btn prim" data-a="redem">Redémarrer le démon…</button></div></div>' + haut + "</section>" +
      '<div class="cols2">' + section("Redémarrages", hist.length ? '<div class="rows">' + hist.map((h) => '<div class="row"><span class="dot ' + (/^échec/.test(h.resultat) ? "dg" : "ok") + '"></span><div class="rt"><b>' + esc(h.qui || "?") + "</b><span>" + esc(h.motif || "sans motif") + '</span><span class="age">' + (h.silence_s != null ? "silence de " + esc(h.silence_s) + " s · " : "") + esc(h.resultat) + '</span></div><span class="age">' + esc(quand(h.ts)) + "</span></div>").join("") + "</div>" : '<div class="note">Aucun redémarrage depuis cette page. Un redémarrage demandé ici, ou fait seul par systemd, se raconte ici.</div>') +
      section("Les modules du noyau", mods && !mods.muet ? (sante.length ? '<div class="rows">' + sante.map((k) => '<div class="row"><span class="dot ' + (mods.modules[k].verdict === "en_echec" ? "dg" : "warn") + '"></span><div class="rt"><b>' + esc(k) + ' <span class="puce ' + (mods.modules[k].verdict === "en_echec" ? "dg" : "al") + '">' + esc(mods.modules[k].verdict === "en_echec" ? "en échec" : "à surveiller") + "</span></b><span>" +
        esc((mods.modules[k].en_echec || mods.modules[k].a_surveiller || []).join(", ") || "des capacités ont été refusées dans les dernières 24 h") + "</span></div></div>").join("") + "</div>" : '<div class="note">Les ' + Object.keys(mods.modules || {}).length + " modules sont sains.</div>") : '<div class="note">' + esc((mods && mods.erreur) || "Santé des modules pas encore relevée.") + "</div>") + "</div>" +
      section("Cassandra vue du dehors", cass.length ? liste(cass) : '<div class="note">Pas encore de relevé du noyau (le démon relit toutes les 5 minutes).</div>', '<span class="note">noyau, bases, code scellé, courtier root</span>');
  }
  function pMaintenance() {
    const f = S.fen || { vivantes: [], finies: [] }, d = new Date(), pad = (n) => String(n).padStart(2, "0"), loc = (x) => x.getFullYear() + "-" + pad(x.getMonth() + 1) + "-" + pad(x.getDate()) + "T" + pad(x.getHours()) + ":" + pad(x.getMinutes());
    const fin = new Date(Date.now() + 3600000);
    const machines = Array.from(new Set(rows().filter((r) => r.objet && r.objet.genre === "Machines").map((r) => r.objet.nom)));
    const portees = '<option value="*">Toute la machine</option>' + domaines().map((x) => '<option value="domaine:' + esc(x[0]) + '">Le domaine « ' + esc(x[1]) + " »</option>").join("") +
      ((S.etat && S.etat.familles) || []).map((x) => '<option value="famille:' + esc(x[0]) + '">La famille « ' + esc(x[1]) + " »</option>").join("") + machines.map((m) => '<option value="machine:' + esc(m) + '">La machine « ' + esc(m) + " »</option>").join("");
    const lf = (x) => '<div class="row"><span class="dot ' + (x.debut <= f.maintenant ? "warn" : "mu") + '"></span><div class="rt"><b>' + esc(String(x.debut).slice(5, 16)) + " → " + esc(String(x.fin).slice(5, 16)) + " <span class=\"note\">(UTC)</span></b><span>" + esc(x.portee === "*" ? "toute la machine" : x.portee) + (x.motif ? " · " + esc(x.motif) : "") + "</span></div>" +
      '<div class="gest"><button class="btn pt" data-a="fen-annuler:' + x.id + '">Annuler</button></div></div>';
    return section("Fenêtres de maintenance", '<p class="vs">Pendant une fenêtre, les relevés continuent mais les constats se taisent. À la fin, ce qui est encore en alerte revient d\'un coup.</p><div class="cols2"><div class="carte"><h2>Planifier</h2>' +
      '<div class="champ"><label for="sx-fp">Ce qui se tait</label><select id="sx-fp">' + portees + '</select></div><div class="champ"><label for="sx-fd">Du</label><input id="sx-fd" type="datetime-local" value="' + loc(d) + '"></div>' +
      '<div class="champ"><label for="sx-ff">Jusqu\'au</label><input id="sx-ff" type="datetime-local" value="' + loc(fin) + '"></div><div class="champ"><label for="sx-fm">Pourquoi</label><input id="sx-fm" placeholder="par exemple : mise à jour du noyau"></div>' +
      '<div class="err" id="sx-fe">' + esc(S.erreur && S.vue === "maintenance" ? S.erreur : "") + '</div><div class="gest" style="justify-content:flex-start"><button class="btn prim" data-a="fen-ok">Planifier</button></div></div>' +
      '<div class="carte"><h2>En cours et à venir</h2>' + (f.vivantes.length ? '<div class="rows">' + f.vivantes.map(lf).join("") + "</div>" : '<div class="note">Aucune fenêtre.</div>') +
      (f.finies.length ? '<span class="lib">Terminées ou annulées</span><div class="rows">' + f.finies.map((x) => '<div class="row"><span class="dot mu"></span><div class="rt"><b>' + esc(String(x.debut).slice(5, 16)) + " → " + esc(String(x.fin).slice(5, 16)) + (x.annulee ? " (annulée)" : "") + "</b><span>" + esc(x.portee === "*" ? "toute la machine" : x.portee) + (x.motif ? " · " + esc(x.motif) : "") + "</span></div></div>").join("") + "</div>" : "") + "</div></div>");
  }
  function pComparer() {
    const c = S.comp, mot = { added: "apparu", removed: "disparu", modified: "changé" };
    const choix = [["1h", "Il y a 1 h"], ["6h", "Il y a 6 h"], ["24h", "Hier à cette heure"], ["7j", "Il y a 7 jours"]];
    const n = (t) => (c ? c.liste.filter((x) => x.change_type === t).length : 0), nees = c ? c.liste.filter((x) => x.severity === "warning").length : 0;
    return section("Comparer deux moments", '<div class="chips">' + choix.map((x) => '<button class="chip' + (S.avant === x[0] ? " on" : "") + '" data-a="comp:' + x[0] + '">' + x[1] + "</button>").join("") + '<span class="note" style="align-self:center">contre maintenant</span></div>' +
      (c ? '<div class="kpis">' + kpi("Apparus", String(n("added"))) + kpi("Disparus", String(n("removed"))) + kpi("Changés", String(n("modified"))) + kpi("En alerte", String(nees)) + "</div>" +
        (c.liste.length ? '<div class="rows">' + c.liste.slice(0, 120).map((x) => '<div class="row"><span class="dot ' + (x.severity === "warning" ? "warn" : "ok") + '"></span><div class="rt"><b>' + esc(x.entity_name) + ' <span class="puce mu">' + esc(mot[x.change_type] || x.change_type) + "</span></b><span>" + esc(x.new_value || x.old_value || "") + "</span>" +
          (x.old_value && x.new_value ? '<span class="age">avant : ' + esc(x.old_value) + "</span>" : "") + '</div><span class="age">' + esc(quand(x.ts)) + "</span></div>").join("") + "</div>" + (c.liste.length > 120 ? '<div class="note">' + (c.liste.length - 120) + " autres non montrés.</div>" : "") : '<div class="note">Rien n\'a changé depuis.</div>') +
        (c.erreur ? '<div class="err">' + esc(c.erreur) + "</div>" : "") : '<div class="note">Lecture…</div>') +
      '<div class="note">Utile après un incident (« qu\'est-ce qui a bougé depuis l\'heure où tout allait bien ? ») ou après un déploiement. Le collecteur rend au plus les 500 derniers changements.</div>');
  }
  function pAlertes() {
    const acc = rows().filter((r) => r.acquit), f = S.fen || { vivantes: [] };
    return section("Ce que tu as accepté", acc.length ? '<div class="rows">' + acc.map((r) => '<div class="row"><span class="dot mu"></span><div class="rt"><b>' + esc(r.libelle || r.wkey) + ' <span class="puce mu">acceptée</span></b><span>« ' + esc(r.acquit.raison || "sans raison") + " » · " + (r.acquit.jusqua ? "jusqu'au " + esc(String(r.acquit.jusqua).slice(0, 10)) : "sans échéance") + " · revient si le chiffre monte</span></div>" +
      '<div class="gest"><button class="btn pt" data-a="ret:' + esc(r.wkey) + '">Ne plus accepter</button></div></div>').join("") + "</div>" : '<div class="note">Aucune alerte acceptée.</div>') +
      section("Fenêtres de maintenance en cours", f.vivantes.length ? '<div class="rows">' + f.vivantes.map((x) => '<div class="row"><span class="dot warn"></span><div class="rt"><b>' + esc(String(x.debut).slice(5, 16)) + " → " + esc(String(x.fin).slice(5, 16)) + '</b><span>' + esc(x.portee === "*" ? "toute la machine" : x.portee) + (x.motif ? " · " + esc(x.motif) : "") + "</span></div></div>").join("") + "</div>" : '<div class="note">Aucune. <a style="color:var(--accent);cursor:pointer" data-a="vue:maintenance">En planifier une</a></div>') +
      pSeuils() + pGravites();
  }
  function pSeuils() {
    const sg = (S.etat && S.etat.seuils) || { liste: [], pose: {} }, pose = sg.pose || {};
    const champ = (x) => '<div class="champ"><label for="sx-s-' + esc(x.id) + '">' + esc(x.libelle) + '</label><input id="sx-s-' + esc(x.id) + '" data-seuil="' + esc(x.id) + '" type="number" min="' + x.min + '" max="' + x.max + '" value="' + x.valeur + '"><span class="note">défaut ' + x.defaut + " · de " + x.min + " à " + x.max + (x.qui === "demon" ? " · appliqué par le démon" : "") + "</span></div>";
    const etat = pose.poses ? '<span class="puce ok">posés chez le démon</span>' : '<span class="puce al" title="' + esc(pose.erreur || "") + '">pas encore posés chez le démon</span>';
    return section("Seuils", '<p class="vs">Ce qui fait passer une mesure en alerte. Les changer repose le fichier du démon tout de suite (commande root du courtier) ; un seuil hors de ses bornes est refusé.</p><div class="cols2">' + sg.liste.map(champ).join("") + "</div>" +
      '<div class="err" id="sx-se">' + esc(S.erreurSeuils || "") + '</div><div class="gest" style="justify-content:flex-start"><button class="btn prim" data-a="seuils-ok">Enregistrer les seuils</button>' + etat + "</div>");
  }
  function pGravites() {
    const gr = (S.etat && S.etat.gravites) || [];
    return section("Qui est prévenu, et comment", '<p class="vs">Une mesure en alerte ouvre un <b>constat</b> (la cloche le montre, le badge du menu le compte) quand sa gravité le permet, après le nombre de relevés réglé ci-dessus ; accepter l\'alerte ou poser une fenêtre le referme. ' +
      "Où la notification part ensuite (Telegram, courriel…) se règle par compte et par gravité, dans Mon compte › Notifications (la politique y existe déjà ; l'envoi par courriel et Telegram viendra avec le module des canaux) : le Sensorium ne choisit que la gravité.</p>" +
      '<div class="rows">' + gr.map((g) => '<div class="row"><span class="dot ' + (g.id === "critique" ? "dg" : g.id === "avoir" ? "warn" : "ok") + '"></span><div class="rt"><b>' + esc(g.libelle) + "</b><span>" + esc(g.dit) + '</span></div><div class="gest"><label class="chip' + (g.ouvre ? " on" : "") + '" style="cursor:pointer"><input type="checkbox" data-grav="' + esc(g.id) + '" ' + (g.ouvre ? "checked" : "") + ' style="margin-right:6px">ouvre un constat</label></div></div>').join("") + "</div>");
  }

  // ── les fenêtres ──────────────────────────────────────────────────────────────
  function htmlModal() {
    const m = S.modal; if (!m) return "";
    const fin = (corps, act) => '<div class="voile" data-a="voile"><div class="modal" role="dialog" aria-modal="true">' + corps + '<div class="act">' + act + "</div></div></div>";
    if (m.type === "accepter") return fin("<h2>Pourquoi « " + esc(m.lib) + " » est-elle normale ?</h2><p class=\"vs\">Elle se taira, et reviendra si son chiffre monte.</p><div class=\"champ\"><label for=\"sx-r\">Raison</label><textarea id=\"sx-r\" rows=\"2\" placeholder=\"par exemple : volume d'archive, plein par conception\"></textarea></div>" +
      '<div class="champ"><label for="sx-j">Pendant combien de jours ? (0 = sans échéance)</label><input id="sx-j" value="30"></div><div class="err">' + esc(m.erreur || "") + "</div>", '<button class="btn" data-a="fermer">Annuler</button><button class="btn prim" data-a="acc-ok">Accepter</button>');
    if (m.type === "reparer") {
      if (m.occupe) return fin("<h2>" + esc(m.libelle) + "</h2>", '<div class="attente"><i></i><span>Le geste tourne à root, je vérifie ensuite… Au plus quelques minutes ; ne ferme pas la page.</span></div>');
      if (m.resultat) return fin('<h2>' + esc(m.libelle) + '</h2><div class="verdict"><span class="vmark ' + (m.resultat.verifie ? "stable" : "") + '"></span><div><p class="vt">' + (m.resultat.verifie ? "Fait, et vérifié" : "Fait, mais pas vérifié") + '</p><p class="vs">' + esc(m.resultat.sortie || "") + "</p></div></div>", '<button class="btn prim" data-a="fermer">Fermer</button>');
      return fin("<h2>" + esc(m.libelle) + " ?</h2><p class=\"vs\">« " + esc(m.lib) + " » — le geste est dans une table fermée, lancé à root par le courtier, vérifié, et écrit au journal. Il ne se défait pas.</p><div class=\"err\">" + esc(m.erreur || "") + "</div>", '<button class="btn" data-a="fermer">Annuler</button><button class="btn prim" data-a="rep-ok">' + esc(m.libelle) + "</button>");
    }
    if (m.type === "temoin") {
      const t = m.t;
      if (!t) return fin("<h2>Témoin extérieur</h2><div class=\"attente\"><i></i><span>Lecture…</span></div>", "");
      const zone = (id, texte) => '<div class="champ"><textarea id="sx-t-' + id + '" rows="' + Math.min(14, texte.split("\n").length + 1) + '" readonly style="font-family:' + MONO + ';font-size:11.5px">' + esc(texte) + '</textarea><div class="gest" style="justify-content:flex-start"><button class="btn pt" data-a="copier:' + id + '">Copier</button></div></div>';
      if (t.manque && t.manque.length) return fin("<h2>Témoin extérieur</h2><p class=\"vs\">Un témoin est un petit script sur UNE AUTRE machine : il interroge ce serveur chaque minute et, après dix minutes de silence, écrit sur Telegram (puis retire son message au retour). Dis-lui d'abord où ce serveur répond.</p>" +
        '<div class="champ"><label for="sx-tu">Adresse publique de Cassandra</label><input id="sx-tu" placeholder="https://cassandra.exemple.fr/"></div><div class="champ"><label for="sx-tl">Adresse sur le réseau local (facultatif)</label><input id="sx-tl" placeholder="http://192.168.1.10:9000/"></div><div class="err">' + esc(m.erreur || "") + "</div>",
        '<button class="btn" data-a="fermer">Annuler</button><button class="btn prim" data-a="temoin-url-ok">Continuer</button>');
      return fin("<h2>Témoin extérieur</h2><p class=\"vs\">Il surveille " + t.urls.map(esc).join(" et ") + ". À poser sur une machine Linux avec <b>curl</b>, qui n'est pas ce serveur. Le jeton de ton robot Telegram et ton identifiant de conversation se remplissent <b>là-bas</b> : Cassandra ne les connaît pas et ne les copie jamais.</p>" +
        '<div class="lib">1 · le dossier</div>' + zone("d", "mkdir -p ~/.cassandra-temoin && chmod 700 ~/.cassandra-temoin") + '<div class="lib">2 · le script (temoin.sh)</div>' + zone("s", t.script) + '<div class="lib">3 · la configuration (config), à remplir : TOKEN et CHAT</div>' + zone("c", t.config) +
        '<div class="lib">4 · le lancer, et le garder en vie (unité systemd utilisateur)</div>' + zone("u", t.unite) + '<div class="note">chmod 700 ~/.cassandra-temoin/temoin.sh · systemctl --user enable --now temoin (après avoir posé l\'unité dans ~/.config/systemd/user/temoin.service). Le battement du témoin n\'est pas relu d\'ici : il se lit sur sa machine (~/.cassandra-temoin/etat).</div>', '<button class="btn prim" data-a="fermer">Fermer</button>');
    }
    if (m.type === "redem") {
      if (m.occupe) return fin("<h2>Redémarrage du démon</h2>", '<div class="attente"><i></i><span>' + (m.quand === "maintenant" ? "Arrêt et relance…" : "J\'attends la fin de la passe en cours, puis je relance…") + " Au plus quelques minutes ; ne ferme pas la page.</span></div>");
      if (m.resultat) return fin("<h2>Redémarrage du démon</h2><div class=\"verdict\"><span class=\"vmark stable\"></span><div><p class=\"vt\">Revenu</p><p class=\"vs\">Silence de " + esc(m.resultat.silence_s) + " s" + (m.resultat.attendu_s ? " · " + esc(m.resultat.attendu_s) + " s d'attente de la passe" : "") + " · processus " + esc((m.resultat.avant || {}).pid) + " → " + esc((m.resultat.apres || {}).pid) + " · version " + esc((m.resultat.apres || {}).version) + "</p></div></div>", '<button class="btn prim" data-a="fermer">Fermer</button>');
      return fin("<h2>Redémarrer le démon du Sensorium</h2><p class=\"vs\">Quelques secondes de silence ; aucune mesure n'est perdue, le démon reprend sa passe. La commande est lancée à root par le courtier et se vérifie : le démon doit répondre avec un autre processus.</p>" +
        '<div class="champ"><label for="sx-q">Quand</label><select id="sx-q"><option value="apres_passe">Après la fin de la passe en cours (recommandé)</option><option value="maintenant">Maintenant, la passe en cours est coupée</option></select></div>' +
        '<div class="champ"><label for="sx-m">Pourquoi</label><input id="sx-m" placeholder="par exemple : déploiement de la 0.1.12"></div><div class="err">' + esc(m.erreur || "") + '</div><div class="note">Un redémarrage ne se défait pas, il se vérifie.</div>', '<button class="btn" data-a="fermer">Annuler</button><button class="btn prim" data-a="redem-ok">Redémarrer</button>');
    }
    return "";
  }

  // ── le dessin ─────────────────────────────────────────────────────────────────
  function titreDe() { return S.histo ? S.histo.lib : S.obj ? S.obj.split("|")[1] : S.fam ? famLib(S.fam) : S.dom != null ? ((domaines()[S.dom] || [])[1] || "") : S.gen ? S.gen : (VUES.find((v) => v[0] === S.vue) || [, ""])[1]; }
  function fil() {
    const l = (t, a) => '<a data-a="' + a + '">' + esc(t) + "</a> › ";
    let c = l("Sensorium", "vue:maintenant");
    if (S.fam) { const d = domaines().findIndex((x) => x[2].indexOf(S.fam) >= 0); if (d >= 0) c += l(domaines()[d][1], "dom:" + d); }
    if (S.obj) c += l(S.obj.split("|")[0], "gen:" + S.obj.split("|")[0]);
    if (S.histo && S.obj) c += l(S.obj.split("|")[1], "retour");
    return '<div class="fil">' + c + "<b>" + esc(titreDe()) + "</b></div>";
  }
  function page() {
    if (S.erreur && !S.etat) return section("Le Sensorium ne répond pas", '<p class="vs">' + esc(S.erreur) + "</p>");
    if (S.etat && S.etat.muet) return '<div class="bandeau dg">Le collecteur ne répond plus : ce qui est affiché date d\'avant, et vieillit. ' + esc(S.etat.erreur || "") + "</div>" + (S.vue === "demon" ? pDemon() : S.vue === "maintenance" ? pMaintenance() : "");
    if (S.histo) return pHistoire();
    if (S.obj) return pObjet();
    if (S.fam) return pFamille();
    if (S.dom != null) return pDomaine();
    if (S.gen) return pGenre();
    const enMaint = rows().filter((r) => r.maintenance && alerte(r)).length;
    return (enMaint ? '<div class="bandeau">' + enMaint + " alerte" + (enMaint > 1 ? "s" : "") + " en maintenance : les relevés continuent, les constats se taisent. <a style=\"cursor:pointer;text-decoration:underline\" data-a=\"vue:maintenance\">Voir</a></div>" : "") +
      ({ maintenant: pMaintenant, changements: pChangements, capteurs: pCapteurs, carte: pCarte, demon: pDemon, maintenance: pMaintenance, comparer: pComparer, alertes: pAlertes }[S.vue] || pMaintenant)();
  }
  function dessiner() {
    if (!racine || !document.body.contains(racine)) return;
    const sx = racine.querySelector("#sx"); if (!sx) return;
    const focus = document.activeElement && document.activeElement.id, q = S.q;
    sx.innerHTML = '<div class="entete"><div><h1>Sensorium</h1><div class="note">' + esc((S.etat && S.etat.hote) || "") + (S.etat && S.etat.lu_a ? " · relevé il y a " + age(new Date(S.etat.lu_a * 1000).toISOString()) : "") + "</div></div>" +
      '<div class="d"><button class="btn" data-a="relever">Relever la flotte</button><button class="btn" data-a="temoin" title="Un script à poser sur une autre machine : il sonne si ce serveur se tait">Témoin extérieur</button></div></div>' + fil() +
      '<div class="rech"><div class="cherche"><input id="sx-q-in" placeholder="Chercher un site, une machine, une mesure, une vue…" autocomplete="off" aria-label="Chercher" value="' + esc(q) + '">' + htmlRecherche() + '</div><button class="btn" data-a="toutes" style="border-radius:12px;padding:10px 14px">Toutes les familles ▾</button></div>' +
      page() + htmlModal();
    if (focus === "sx-q-in" && S.ouvrir === "q") { const i = sx.querySelector("#sx-q-in"); if (i) { i.focus(); i.setSelectionRange(q.length, q.length); } }       // le focus ne revient que si la recherche est ouverte : sinon son retour la rouvrirait
  }

  // ── les gestes ────────────────────────────────────────────────────────────────
  async function agirEtRecharger(cap, args, apres) {
    S.occupe = true;
    try { await agir(cap, args); S.erreur = ""; if (apres) apres(); await charger(); } catch (e) { return e.message || String(e); } finally { S.occupe = false; }
    return "";
  }
  async function clic(a) {
    const [k, ...r] = a.split(":"), v = r.join(":");
    if (k === "voile") return;
    if (k === "vue") return aller(v);
    if (k === "fam") { S.obj = S.histo = null; S.dom = S.gen = null; S.fam = v; S.q = ""; S.ouvrir = ""; S.filtre = "tous"; return dessiner(); }
    if (k === "dom") { S.fam = S.obj = S.histo = null; S.gen = null; S.dom = Number(v); S.q = ""; S.ouvrir = ""; return dessiner(); }
    if (k === "gen") { S.fam = S.obj = S.histo = null; S.dom = null; S.gen = v; S.q = ""; S.ouvrir = ""; return dessiner(); }
    if (k === "obj") { S.fam = S.histo = null; S.dom = S.gen = null; S.obj = v; S.q = ""; S.ouvrir = ""; return dessiner(); }
    if (k === "histo") { S.q = ""; S.ouvrir = ""; await histoire(v); return dessiner(); }
    if (k === "retour") { S.histo = null; return dessiner(); }
    if (k === "filtre") { S.filtre = v; return dessiner(); }
    if (k === "toutes") { S.ouvrir = S.ouvrir === "fam" ? "" : "fam"; S.q = ""; return dessiner(); }
    if (k === "relever") { try { await agir("flotte.parc"); CASS.kit && CASS.kit.dire && CASS.kit.dire("Relevé de la flotte lancé", "ok"); } catch (e) { S.erreur = ""; if (CASS.kit && CASS.kit.dire) CASS.kit.dire("Le relevé de la flotte n'est pas disponible : " + (e.message || e), "err"); } return; }
    if (k === "acc") { S.modal = { type: "accepter", wkey: v, lib: ((rows().find((x) => x.wkey === v) || {}).libelle) || v }; return dessiner(); }
    if (k === "acc-ok") {
      const raison = (racine.querySelector("#sx-r") || {}).value || "", jours = (racine.querySelector("#sx-j") || {}).value;
      const e = await agirEtRecharger("sensorium.accepter", { wkey: S.modal.wkey, raison: raison, jours: parseInt(jours, 10) || 0 }, () => { S.modal = null; });
      if (e) S.modal.erreur = e; return dessiner();
    }
    if (k === "ret") { const e = await agirEtRecharger("sensorium.retirer_acceptation", { wkey: v }); if (e) S.erreur = e; return dessiner(); }
    if (k === "fermer") { S.modal = null; return dessiner(); }
    if (k === "fen-ok") {
      const val = (id) => (racine.querySelector(id) || {}).value || "", utc = (x) => { const d = new Date(x); return isNaN(d) ? "" : d.toISOString().slice(0, 19).replace("T", " "); };
      const e = await agirEtRecharger("sensorium.fenetre_poser", { portee: val("#sx-fp"), debut: utc(val("#sx-fd")), fin: utc(val("#sx-ff")), motif: val("#sx-fm") }, () => { S.fen = null; });
      S.erreur = e; S.fen = await agir("sensorium.fenetres").catch(() => null); return dessiner();
    }
    if (k === "fen-annuler") { const e = await agirEtRecharger("sensorium.fenetre_annuler", { id: Number(v) }); S.erreur = e; S.fen = await agir("sensorium.fenetres").catch(() => null); return dessiner(); }
    if (k === "comp") { S.avant = v; S.comp = null; dessiner(); await chargerComparaison(); return dessiner(); }
    if (k === "rep") {
      const [wk, g] = v.split("|"), r = rows().find((x) => x.wkey === wk), geste = r && (r.gestes || []).find((x) => x.id === g);
      S.modal = { type: "reparer", wkey: wk, geste: g, lib: r ? r.libelle : wk, libelle: geste ? geste.libelle : g }; return dessiner();
    }
    if (k === "rep-ok") {
      const m = S.modal; S.modal = { type: "reparer", occupe: true, libelle: m.libelle }; dessiner();
      try { S.modal = { type: "reparer", libelle: m.libelle, resultat: await agir("sensorium.reparer", { wkey: m.wkey, geste: m.geste }) }; }
      catch (e) { S.modal = Object.assign({}, m, { erreur: e.message || String(e) }); }
      await charger(); return dessiner();
    }
    if (k === "grav") return;
    if (k === "seuils-ok") {
      const champs = Array.from(racine.querySelectorAll("[data-seuil]")), faits = [];
      let erreur = "";
      for (const c of champs) {
        const x = ((S.etat.seuils || {}).liste || []).find((y) => y.id === c.dataset.seuil), n = parseInt(c.value, 10);
        if (!x || n === x.valeur) continue;
        if (isNaN(n) || n < x.min || n > x.max) { erreur = x.libelle + " : un entier entre " + x.min + " et " + x.max + " est attendu"; break; }
        faits.push([x.id, n]);
      }
      if (!erreur) for (const f of faits) { try { await agir("reglages.regler", { cle: "sensorium." + f[0], valeur: f[1] }); } catch (e) { erreur = e.message || String(e); break; } }
      if (!erreur && faits.length) { try { await agir("sensorium.seuils_pousser"); } catch (e) { erreur = "enregistrés, mais pas posés chez le démon : " + (e.message || e); } }
      S.erreurSeuils = erreur; await charger(); return dessiner();
    }
    if (k === "temoin") { S.modal = { type: "temoin" }; dessiner(); try { S.modal = { type: "temoin", t: await agir("sensorium.temoin") }; } catch (e) { S.modal = { type: "temoin", t: { manque: ["temoin_url_publique"], urls: [] }, erreur: e.message || String(e) }; } return dessiner(); }
    if (k === "temoin-url-ok") {
      const u = (racine.querySelector("#sx-tu") || {}).value || "", l = (racine.querySelector("#sx-tl") || {}).value || "";
      try { await agir("reglages.regler", { cle: "sensorium.temoin_url_publique", valeur: u.trim() }); await agir("reglages.regler", { cle: "sensorium.temoin_url_lan", valeur: l.trim() }); S.modal = { type: "temoin", t: await agir("sensorium.temoin") }; }
      catch (e) { S.modal.erreur = e.message || String(e); }
      return dessiner();
    }
    if (k === "copier") {
      const z = racine.querySelector("#sx-t-" + v); if (!z) return;
      try { await navigator.clipboard.writeText(z.value); if (CASS.kit && CASS.kit.dire) CASS.kit.dire("Copié", "ok"); } catch (e) { z.focus(); z.select(); }
      return;
    }
    if (k === "redem") { S.modal = { type: "redem" }; return dessiner(); }
    if (k === "redem-ok") {
      const quandR = (racine.querySelector("#sx-q") || {}).value || "apres_passe", motif = (racine.querySelector("#sx-m") || {}).value || "";
      S.modal = { type: "redem", occupe: true, quand: quandR }; dessiner();
      try { const r = await agir("sensorium.redemarrer", { quand: quandR, motif: motif }); S.modal = { type: "redem", resultat: r }; }
      catch (e) { S.modal = { type: "redem", erreur: e.message || String(e) }; }
      S.demon = await agir("sensorium.demon").catch(() => S.demon); return dessiner();
    }
  }
  function brancher() {
    racine.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-a]");
      if (!b || !racine.contains(b)) { if (S.ouvrir && !ev.target.closest(".cherche")) { S.ouvrir = ""; dessiner(); } return; }
      if (b.dataset.a === "voile" && ev.target !== b) return;                 // un clic dans la fenêtre ne la ferme pas
      ev.preventDefault(); clic(b.dataset.a);
    });
    racine.addEventListener("change", async (ev) => {
      const c = ev.target.closest("[data-grav]"); if (!c) return;
      try { await agir("reglages.regler", { cle: "sensorium.constat_" + c.dataset.grav, valeur: !!c.checked }); } catch (e) { S.erreur = e.message || String(e); }
      await charger(); dessiner();
    });
    racine.addEventListener("input", (ev) => { if (ev.target.id === "sx-q-in") { S.q = ev.target.value; S.ouvrir = "q"; dessiner(); } });
    racine.addEventListener("focusin", (ev) => { if (ev.target.id === "sx-q-in" && S.ouvrir !== "q") { S.ouvrir = "q"; dessiner(); } });
    racine.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") { if (S.modal) { S.modal = null; } S.ouvrir = ""; dessiner(); return; }
      if (ev.target.id === "sx-q-in" && ev.key === "Enter") { const r = resultats()[0]; if (r) clic(r.go); }
    });
  }

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.sensorium = async function (corps, ctx) {
    css(); racine = corps;
    const v = window.__sxVue; window.__sxVue = null;
    const ecran = ctx && ctx.ecran ? String(ctx.ecran).split(":")[1] : "";
    S.vue = v || (VUES.some((x) => x[0] === ecran) ? ecran : S.vue) || "maintenant";
    S.fam = S.obj = S.histo = null; S.dom = S.gen = null; S.modal = null; S.q = ""; S.ouvrir = ""; S.etat = null;
    corps.innerHTML = '<div class="sx" id="sx"><div class="note">Lecture du Sensorium…</div></div>';
    brancher();
    await charger(); dessiner();
    clearInterval(timer);
    timer = setInterval(async () => {
      if (!document.body.contains(racine)) return clearInterval(timer);
      if (S.modal || S.occupe || S.ouvrir || (document.activeElement && /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))) return;
      if (!racine.offsetParent) return;                                     // l'onglet n'est pas à l'écran : on ne relit pas
      await charger(); dessiner();
    }, 30000);
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : l'écran du module Sensorium. Il n'appelle que les capacités du module (etat, demon, modules, fenetres, changements, historique, accepter, retirer_acceptation, fenetre_poser, fenetre_annuler, redemarrer, + flotte.parc) et n'invente aucune donnée :
//      ce qui n'a pas de moteur garde la pastille « non branché » et aucun chiffre (aujourd'hui : rien).
// EC : néant. Une vue évolutive serait déclarative (jamais du script) : docs/CN_NEXUS.md §5 bis.
// LIEN : modules/sensorium (le module et son démon), docs/maquettes/CN_maquette-sensorium.html (la maquette), interface/CN_shell.js (le crochet CASS.sceneSurMesure et remplacerV18).
