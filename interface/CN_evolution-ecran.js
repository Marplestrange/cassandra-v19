// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Évolution : l'écran (cibles, pièces, versions, chaîne, gestes)
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #21d126
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : dessine l'écran du module Évolution à partir de ses capacités : ce qui existe, rien d'inventé.
// MÉTHODE    : un crochet de la scène (CASS.sceneSurMesure.evolution) ; données par evolution.etat, gestes par evolution.proposer / retour / visiter ; tout texte dynamique est échappé.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=21d126 ▼▼▼
/* L'écran de l'Évolution (maquette docs/CN_maquette-evolution.html, réalisée avec ce qui est CONSTRUIT).

   Rien n'est affiché qui n'existe pas : pas de « nuit rejouée », pas de fossilisation, pas de chiffre d'autonomie. Ce que le noyau sait dire, cet écran le dit ;
   ce qu'il ne sait pas encore faire est listé à part, en bas, comme tel.
   Les gestes disent leur risque, leur preuve et leur retour AVANT d'agir, et une confirmation dans la page (jamais une boîte du navigateur). */
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const token = () => { try { return sessionStorage.getItem("cassandra_session") || ""; } catch (e) { return ""; } };

  const CSS = ".ev{display:flex;flex-direction:column;gap:14px;color:var(--txt)}" +
    ".ev h3,.ev h4{margin:0;font-weight:600;color:var(--txt-strong)}" +
    ".ev-bandeau{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}" +
    ".ev-carte{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;box-shadow:var(--shadow-glass);min-width:0}" +
    ".ev-lib{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-muted);margin-bottom:6px}" +
    ".ev-v{font:600 22px/1.1 ui-monospace,Menlo,Consolas,monospace;color:var(--txt-strong)}" +
    ".ev-v small{font-size:12px;color:var(--txt-muted);font-weight:400}" +
    ".ev-note{font-size:12px;color:var(--txt-muted);line-height:1.45}" +
    ".ev-cols{display:grid;grid-template-columns:260px minmax(0,1fr) 330px;gap:14px;align-items:start}" +
    "@media(max-width:1150px){.ev-cols{grid-template-columns:1fr}}" +
    ".ev-rail{display:flex;flex-direction:column;gap:6px}" +
    ".ev-cible{text-align:left;border:1px solid transparent;border-radius:12px;padding:9px 10px;background:transparent;color:inherit;cursor:pointer;display:flex;flex-direction:column;gap:4px;width:100%;font:inherit}" +
    ".ev-cible:hover{background:var(--ov-04)}.ev-cible.sel{background:var(--surface);border-color:var(--accent)}" +
    ".ev-cible b{font:600 12px ui-monospace,Menlo,Consolas,monospace;word-break:break-all}" +
    ".ev-puces{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:11.5px;color:var(--txt-muted)}" +
    ".ev-puce{display:inline-block;border-radius:99px;padding:2px 8px;font:600 10.5px ui-monospace,Menlo,Consolas,monospace;background:var(--ov-06);color:var(--txt-soft)}" +
    ".ev-puce.ok{background:var(--ok-soft,rgba(4,120,87,.12));color:var(--ok)}.ev-puce.warn{background:rgba(180,83,9,.12);color:var(--warn)}.ev-puce.bad{background:var(--danger-soft);color:var(--danger)}" +
    ".ev-onglets{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:8px}" +
    ".ev-onglets button{border:0;background:transparent;border-radius:9px;padding:6px 12px;font:600 12px ui-monospace,Menlo,Consolas,monospace;color:var(--txt-muted);cursor:pointer}" +
    ".ev-onglets button.on{background:var(--ov-08);color:var(--accent)}" +
    ".ev table{border-collapse:collapse;width:100%;font-size:12.5px}.ev th,.ev td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}" +
    ".ev th{font:600 10.5px ui-monospace,Menlo,Consolas,monospace;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-muted)}" +
    ".ev .mono{font-family:ui-monospace,Menlo,Consolas,monospace}" +
    ".ev-btn{border:1px solid var(--line-strong);background:var(--surface);color:var(--txt);border-radius:10px;padding:7px 12px;font:600 12px ui-monospace,Menlo,Consolas,monospace;cursor:pointer}" +
    ".ev-btn:hover{border-color:var(--accent)}.ev-btn.prim{background:var(--accent);color:var(--on-accent);border-color:transparent}.ev-btn.dng{color:var(--danger);border-color:var(--danger)}" +
    ".ev-btn[disabled]{opacity:.5;cursor:not-allowed}" +
    ".ev-ligne{display:flex;gap:8px;flex-wrap:wrap;align-items:center}" +
    ".ev select,.ev input[type=number]{border:1px solid var(--line-strong);background:var(--surface);color:var(--txt);border-radius:9px;padding:6px 9px;font:12.5px ui-monospace,Menlo,Consolas,monospace}" +
    ".ev-verdict{border-radius:12px;padding:10px 12px;font-size:12.5px;line-height:1.5}.ev-verdict.ok{background:rgba(4,120,87,.1);color:var(--ok)}" +
    ".ev-verdict.warn{background:rgba(180,83,9,.1);color:var(--warn)}.ev-verdict.bad{background:var(--danger-soft);color:var(--danger)}" +
    ".ev-preuve{border-left:2px solid var(--line-strong);padding-left:10px;font-size:12px;color:var(--txt-soft);line-height:1.5}" +
    ".ev-vide{padding:18px 4px;color:var(--txt-muted);font-size:13px}" +
    ".ev details{border:1px dashed var(--line-strong);border-radius:12px;padding:10px 12px;font-size:12.5px;color:var(--txt-soft)}" +
    ".ev summary{cursor:pointer;font:600 11px ui-monospace,Menlo,Consolas,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-muted)}";

  // ce que chaque geste dit AVANT d'agir (le miroir du manifeste du module)
  const GESTES = {
    proposer: { risque: "moyen", perimetre: "le stock d'EC du point visé : une variante prouvée y est écrite et mise en OMBRE ; rien n'est servi à personne",
                preuve: "la pièce est dans le stock, en ombre, et la chaîne d'empreintes est intacte (ou rien n'a été écrit)", retour: "retirer la pièce : un aiguillage vers la référence ; l'EC reste dans le stock, jamais détruite" },
    retour: { risque: "moyen", perimetre: "le routage du point visé et ses pièces vivantes", preuve: "le routage du point est à l'arrêt", retour: "proposer de nouveau une variante : une pièce retirée ne se remet pas en service seule" },
    visiter: { risque: "moyen", perimetre: "les pièces en service depuis plus de 30 jours, une fois chacune", preuve: "chaque pièce visitée porte son verdict", retour: "aucun : une pièce retirée à la visite se propose de nouveau" }
  };
  const ETATS = { ombre: ["en ombre", "warn"], palier_10: ["10 % du trafic", "warn"], palier_50: ["50 % du trafic", "warn"], en_service: ["en service", "ok"], retiree: ["retirée", "bad"] };
  const VIVANTES = ["ombre", "palier_10", "palier_50", "en_service"];
  const NON_CONSTRUIT = ["La nuit rejouée (rejeu accéléré de la veille contre toutes les variantes)", "La guérison automatique d'une panne (reproduction en test rouge puis correction)", "La fossilisation des décisions de modèle en règles de code",
    "Le routage sur mesure par contexte (variante choisie par type d'appel)", "L'évolution des prompts et des politiques (génome prompts, génome politiques)", "L'objectif écrit en français, compilé en mesure", "Le capital d'EC en jetons et le coût par point de gain",
    "La machine à remonter le temps (restauration de l'organisme à un jour donné)", "L'échange de variantes entre instances"];

  const date = (t) => { try { return new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };
  const ms = (v) => (v == null ? "—" : (v < 1 ? v.toFixed(3) : v.toFixed(2)) + " ms");
  const pct = (v) => (v == null ? "—" : (v > 0 ? "−" : v < 0 ? "+" : "") + Math.abs(v).toFixed(1) + " %");
  const puce = (txt, cls) => '<span class="ev-puce' + (cls ? " " + cls : "") + '">' + esc(txt) + "</span>";

  function style() {
    if (document.getElementById("ev-css")) return;
    const s = document.createElement("style");
    s.id = "ev-css"; s.textContent = CSS; document.head.appendChild(s);
  }

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.evolution = async function (corps, ctx) {
    style();
    const S = { etat: null, versions: {}, sel: null, onglet: "apercu", resultat: null, confirmer: null, occupe: false, erreur: "" };
    const racine = document.createElement("div");
    racine.className = "ev";
    corps.appendChild(racine);

    const point = (gid) => (S.etat.points || []).find((p) => p.point === gid);
    const pieces = (gid) => (S.etat.pieces || []).filter((p) => p.gid === gid);
    const vivante = (gid) => pieces(gid).find((p) => VIVANTES.indexOf(p.etat) >= 0);
    const module = (gid) => gid.split(".")[0];
    const version = (gid) => { const p = vivante(gid); const v = S.versions[module(gid)] || "?"; return p ? v + "+EC" + p.num + "." + p.empreinte : v; };

    async function charger() {
      try {
        S.etat = await CASS.agir("evolution.etat", {});
        if (!S.sel && S.etat.cibles.length) S.sel = S.etat.cibles[0].point;
        if (S.sel && !S.etat.cibles.some((c) => c.point === S.sel)) S.sel = S.etat.cibles.length ? S.etat.cibles[0].point : null;
        S.erreur = "";
      } catch (e) { S.erreur = e.message || String(e); }
      try {
        const d = await (await fetch("/api/modules", { headers: { "X-Session-Token": token() } })).json();
        (d.modules || []).forEach((m) => { S.versions[m.id] = m.version; });
      } catch (e) { /* les versions restent « ? » : dites, pas inventées */ }
    }

    // ── le bandeau ───────────────────────────────────────────────────────
    function bandeau() {
      const tous = S.etat.pieces || [];
      const viv = tous.filter((p) => VIVANTES.indexOf(p.etat) >= 0), enServ = tous.filter((p) => p.etat === "en_service"), ret = tous.filter((p) => p.etat === "retiree");
      const tombes = Object.values(S.etat.tombes || {}).reduce((a, b) => a + b, 0);
      const ch = S.etat.chaine || {};
      const corpus = (S.etat.points || []).reduce((a, p) => a + ((p.corpus || {}).distincts || 0), 0);
      return '<div class="ev-bandeau">' +
        '<div class="ev-carte"><div class="ev-lib">Points d\'évolution</div><div class="ev-v">' + (S.etat.cibles || []).length + '</div><div class="ev-note">déclarés par les modules actifs</div></div>' +
        '<div class="ev-carte"><div class="ev-lib">Pièces vivantes</div><div class="ev-v">' + viv.length + ' <small>dont ' + enServ.length + ' en service</small></div><div class="ev-note">ombre, paliers ou service complet</div></div>' +
        '<div class="ev-carte"><div class="ev-lib">Retirées · tombes</div><div class="ev-v">' + ret.length + ' <small>· ' + tombes + '</small></div><div class="ev-note">une variante échouée n\'est jamais reproposée</div></div>' +
        '<div class="ev-carte"><div class="ev-lib">Corpus de rejeu</div><div class="ev-v">' + corpus + ' <small>entrées</small></div><div class="ev-note">appels réels gardés, un cinquième réservé</div></div>' +
        '<div class="ev-carte"><div class="ev-lib">Chaîne d\'empreintes</div><div class="ev-v">' + (ch.ok ? "✓" : "✗") + ' <small>' + (ch.mailles || 0) + ' maillons</small></div><div class="ev-note">' +
        (ch.ok ? "chaque événement est scellé" : "<b>rupture à la maille " + esc(ch.rupture_a) + " : rien ne doit avancer</b>") + "</div></div></div>";
    }

    // ── le rail des cibles ───────────────────────────────────────────────
    function rail() {
      const l = (S.etat.cibles || []).map((c) => {
        const v = vivante(c.point), e = v ? ETATS[v.etat] : null;
        return '<button class="ev-cible' + (c.point === S.sel ? " sel" : "") + '" data-cible="' + esc(c.point) + '"><b>' + esc(c.point) + "</b><div class=\"ev-puces\">" +
          (e ? puce(e[0], e[1]) : "") + (c.muet ? puce("muet", "") : "") + "<span>" + c.corpus + " entrées</span>" +
          (c.valeur_ms != null ? "<span>valeur " + c.valeur_ms + " ms</span>" : "") + "</div></button>";
      }).join("");
      return '<div class="ev-carte"><div class="ev-lib">Cibles — classées par ce que l\'optimisation rapporterait</div><div class="ev-rail">' +
        (l || '<div class="ev-vide">Aucun module actif ne déclare de point d\'évolution.</div>') + '</div>' +
        '<div class="ev-note" style="margin-top:8px">Valeur = appels réels × durée moyenne. Un point sans mesure est dit <b>muet</b> : il n\'est pas « à zéro », il n\'est pas mesuré.</div></div>';
    }

    // ── le centre ────────────────────────────────────────────────────────
    function centre() {
      if (!S.sel) return '<div class="ev-carte"><div class="ev-vide">Choisis un point à gauche.</div></div>';
      const c = S.etat.cibles.find((x) => x.point === S.sel) || {}, p = point(S.sel) || {}, corpus = p.corpus || {};
      const onglets = [["apercu", "Aperçu"], ["pieces", "Pièces"], ["versions", "Versions"], ["chaine", "Chaîne"]];
      let contenu = "";
      if (S.onglet === "apercu") contenu = apercu(c, p, corpus);
      else if (S.onglet === "pieces") contenu = tablePieces();
      else if (S.onglet === "versions") contenu = versions();
      else contenu = chaine();
      return '<div class="ev-carte" style="display:flex;flex-direction:column;gap:12px"><div><h3 class="mono" style="font-size:15px">' + esc(S.sel) + '</h3><div class="ev-puces" style="margin-top:6px">' +
        puce(version(S.sel)) + puce("contrat " + esc(p.contrat || "?")) + (p.suspendue ? puce("suspendue", "bad") : "") + "</div></div>" +
        '<div class="ev-onglets">' + onglets.map((o) => '<button data-onglet="' + o[0] + '" class="' + (o[0] === S.onglet ? "on" : "") + '">' + o[1] + "</button>").join("") + "</div>" + contenu + "</div>";
    }
    function apercu(c, p, corpus) {
      const v = vivante(S.sel), o = p.ombre, r = p.routage;
      let h = '<div class="ev-bandeau">' +
        '<div class="ev-carte"><div class="ev-lib">Appels réels</div><div class="ev-v">' + (c.appels || 0) + '</div></div>' +
        '<div class="ev-carte"><div class="ev-lib">Durée moyenne</div><div class="ev-v">' + (c.duree_moyenne_ms == null ? "—" : c.duree_moyenne_ms + " <small>ms</small>") + '</div>' + (c.muet ? '<div class="ev-note">muet : jamais mesuré</div>' : "") + "</div>" +
        '<div class="ev-carte"><div class="ev-lib">Corpus</div><div class="ev-v">' + (corpus.distincts || 0) + '</div><div class="ev-note">' + (corpus.visible || 0) + " visibles · " + (corpus.reserve || 0) + " réservées · " + (corpus.dores || 0) + " dorées</div></div></div>";
      if (!v) {
        h += '<div class="ev-verdict ok">Toute la charge passe par la <b>référence du dépôt</b>. Aucune variante n\'est en ombre ni en service sur ce point.</div>';
      } else {
        const e = ETATS[v.etat];
        h += '<div class="ev-carte"><div class="ev-lib">Pièce EC' + v.num + "</div><div class=\"ev-puces\">" + puce(e[0], e[1]) + puce("empreinte " + v.empreinte) + puce("créée " + date(v.cree)) + "</div>" +
          '<div class="ev-note" style="margin-top:8px">Gain annoncé à l\'évaluation : <b>' + pct(v.gain_annonce) + "</b>" + (v.mise_en_service ? " · en service depuis " + date(v.mise_en_service) : "") + "</div>" +
          (r ? '<div class="ev-note">Routage : <b>' + esc(r.mode) + "</b>" + (r.mode === "service" ? " à " + r.part + " %" : "") + "</div>" : "") + "</div>";
        if (o) h += '<div class="ev-carte"><div class="ev-lib">Ombre : l\'EC calcule à côté, la référence répond</div><div class="ev-bandeau">' +
          '<div><div class="ev-lib">Appels comparés</div><div class="ev-v">' + o.appels + '</div></div><div><div class="ev-lib">Écarts</div><div class="ev-v">' + o.ecarts + '</div></div>' +
          '<div><div class="ev-lib">Erreurs</div><div class="ev-v">' + o.erreurs + '</div></div><div><div class="ev-lib">Gain observé</div><div class="ev-v">' + pct(o.gain_pct) + "</div></div></div>" +
          '<div class="ev-note" style="margin-top:6px">Référence ' + ms(o.ref_ms) + " · EC " + ms(o.ec_ms) + ". Un seul écart bloque la promotion ; trois écarts en dix minutes suspendent l'EC.</div></div>";
        const s = S.etat.seuils || {};
        h += '<div class="ev-note">Paliers : ombre sans écart (' + (s.ombre_appels || "?") + " appels), puis " + (s.paliers || []).join(" % → ") + " % du trafic, " + (s.appels_par_palier || "?") + " appels par palier. Le moteur périodique les fait avancer seulement si les preuves tiennent.</div>";
      }
      if (p.suspendue) h += '<div class="ev-verdict bad">EC suspendue par le disjoncteur : ' + esc(p.suspendue.raison) + ". La référence sert ; l'EC est conservée.</div>";
      return h;
    }
    function tablePieces() {
      const l = pieces(S.sel);
      if (!l.length) return '<div class="ev-vide">Aucune pièce sur ce point. Une pièce naît quand le noyau prouve une variante proposée.</div>';
      return "<table><tr><th>EC</th><th>État</th><th>Gain annoncé</th><th>Empreinte</th><th>Créée</th><th>Visite</th></tr>" + l.slice().reverse().map((p) => {
        const e = ETATS[p.etat] || [p.etat, ""], v = p.visite ? JSON.parse(p.visite) : null;
        return '<tr><td class="mono">EC' + p.num + "</td><td>" + puce(e[0], e[1]) + '</td><td class="mono">' + pct(p.gain_annonce) + '</td><td class="mono">' + esc(p.empreinte) + "</td><td>" + date(p.cree) + "</td><td>" +
          (v ? (v.tenu ? puce("gain confirmé", "ok") : puce("gain perdu : " + pct(v.gain_mesure_pct), "bad")) : '<span class="ev-note">à 30 jours</span>') + "</td></tr>";
      }).join("") + "</table>";
    }
    function versions() {
      const m = module(S.sel), dep = S.versions[m] || "?", p = vivante(S.sel);
      return '<div class="ev-note"><b>Version dépôt</b> : celle du dépôt, signée, que personne ne modifie. <b>Version EC</b> (Evolution Cassandra) : l\'état de la ligne évoluée posée par-dessus. Le numéro EC ne repart jamais à zéro ; l\'empreinte l\'accroche au contenu.</div>' +
        '<div class="ev-bandeau"><div class="ev-carte"><div class="ev-lib">Version dépôt · module ' + esc(m) + '</div><div class="ev-v">' + esc(dep) + '</div></div>' +
        '<div class="ev-carte"><div class="ev-lib">Version EC en service</div><div class="ev-v">' + (p ? "EC" + p.num : "—") + '</div><div class="ev-note">' + (p ? "empreinte " + esc(p.empreinte) : "aucune : la référence du dépôt sert (EC0)") + "</div></div>" +
        '<div class="ev-carte"><div class="ev-lib">Écriture complète</div><div class="ev-v" style="font-size:15px">' + esc(version(S.sel)) + "</div></div></div>" +
        '<div class="ev-note">Une EC ne change jamais le manifeste, les signatures de capacités ni les permissions : elle ne remplace que la fonction pure du point, sous le contrat et le disjoncteur du noyau.</div>';
    }
    function chaine() {
      const l = (S.etat.journal || []).filter((e) => e.gid === S.sel);
      if (!l.length) return '<div class="ev-vide">Aucun événement sur ce point. Chaque proposition, ombre, palier, retrait et visite sera scellé ici.</div>';
      return "<table><tr><th>#</th><th>Quand</th><th>Événement</th><th>Détail</th></tr>" + l.map((e) => '<tr><td class="mono">' + e.seq + "</td><td>" + date(e.ts) + '</td><td class="mono">' + esc(e.verbe) + '</td><td class="ev-note">' +
        esc(Object.keys(e.details || {}).map((k) => k + " : " + e.details[k]).join(" · ")) + "</td></tr>").join("") + "</table>";
    }

    // ── le panneau des gestes ────────────────────────────────────────────
    function preuveDe(nom) {
      const g = GESTES[nom];
      return '<div class="ev-preuve"><b>Risque</b> ' + esc(g.risque) + " · <b>Périmètre</b> " + esc(g.perimetre) + "<br><b>Preuve</b> " + esc(g.preuve) + "<br><b>Retour</b> " + esc(g.retour) + "</div>";
    }
    function gestes() {
      const gid = S.sel, v = gid ? vivante(gid) : null;
      let h = '<div class="ev-carte" style="display:flex;flex-direction:column;gap:12px"><h4 class="mono" style="font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-muted)">Gestes</h4>';
      if (!gid) return h + '<div class="ev-vide">Aucun point choisi.</div></div>';
      h += '<div><div class="ev-lib">Proposer une variante</div><div class="ev-ligne"><select id="ev-moteur"><option value="deterministe">Orfan déterministe (zéro jeton)</option><option value="modele">Modèle de langage</option>' +
        '<option value="les_deux">Les deux, gratuit d\'abord</option></select><input type="number" id="ev-budget" min="1" max="10" value="3" style="width:64px" title="variantes évaluées"></div></div>';
      if (S.confirmer === "proposer") h += preuveDe("proposer") + '<div class="ev-ligne"><button class="ev-btn prim" data-geste="proposer-ok"' + (S.occupe ? " disabled" : "") + '>Confirmer : proposer</button><button class="ev-btn" data-geste="annuler">Annuler</button></div>';
      else h += '<div class="ev-ligne"><button class="ev-btn prim" data-geste="proposer"' + (S.occupe ? " disabled" : "") + ">Proposer une variante</button></div>";
      if (v) {
        h += '<div><div class="ev-lib">Retour instantané</div></div>';
        if (S.confirmer === "retour") h += preuveDe("retour") + '<div class="ev-ligne"><button class="ev-btn dng" data-geste="retour-ok"' + (S.occupe ? " disabled" : "") + '>Confirmer : renvoyer à la référence</button><button class="ev-btn" data-geste="annuler">Annuler</button></div>';
        else h += '<div class="ev-ligne"><button class="ev-btn dng" data-geste="retour">Renvoyer toute la charge à la référence</button></div>';
      }
      if (S.confirmer === "visiter") h += '<div><div class="ev-lib">Visite à 30 jours</div></div>' + preuveDe("visiter") + '<div class="ev-ligne"><button class="ev-btn" data-geste="visiter-ok">Confirmer : lancer les visites échues</button><button class="ev-btn" data-geste="annuler">Annuler</button></div>';
      else h += '<div><div class="ev-lib">Visite à 30 jours</div><div class="ev-ligne"><button class="ev-btn" data-geste="visiter">Lancer les visites échues</button></div></div>';
      h += resultat();
      const s = S.etat.seuils || {};
      h += '<div class="ev-note"><b>Ce que le noyau exige avant d\'écrire quoi que ce soit</b> : équivalence sur tout le corpus ; gain d\'au moins ' + (s.gain_min_pct || "?") + " % <i>et</i> deux fois le bruit de mesure, qui tient sur le jeu réservé ; un corpus assez fort (" +
        Math.round(100 * (s.pieges_min || 0)) + " % des variantes fausses attrapées). Sinon : rien n'est écrit.</div></div>";
      return h;
    }
    function resultat() {
      const r = S.resultat;
      if (!r) return "";
      if (r.erreur) return '<div class="ev-verdict bad">' + esc(r.erreur) + "</div>";
      if (r.visites) return '<div class="ev-verdict ' + (r.visites.length ? "ok" : "warn") + '">' + (r.visites.length ? r.visites.map((v) => esc(v.point + " " + v.ec + " : " + (v.tenu ? "gain confirmé" : "gain perdu, pièce retirée"))).join("<br>") : "Aucune visite échue : aucune pièce n'est en service depuis 30 jours.") + "</div>";
      if (r.retraits) return '<div class="ev-verdict ok">' + (r.retraits.length ? "Retour fait : " + r.retraits.map((x) => esc(x.ec)).join(", ") + " retirée(s). La référence sert." : "Rien à retirer.") + "</div>";
      let h = '<div class="ev-verdict ' + (r.ok ? "ok" : "warn") + '">' + (r.ok ? "Variante prouvée, écrite et mise en <b>ombre</b> : " + esc(r.piece.ec) + " (gain annoncé " + pct(r.piece.gain_annonce_pct) + "). Rien n'est encore servi à personne." : "Rien n'a été écrit : " + esc(r.raison)) + "</div>";
      if ((r.essais || []).length) h += "<table><tr><th>Essai</th><th>Verdict</th><th>Gain</th></tr>" + r.essais.map((e, i) => "<tr><td>" + (i + 1) + "</td><td>" + esc(e.verdict) + '</td><td class="mono">' + pct(e.gain_pct) + "</td></tr>").join("") + "</table>";
      if (r.pieges) h += '<div class="ev-note">L\'évaluateur s\'est testé lui-même : ' + (r.pieges.score != null ? Math.round(100 * r.pieges.score) + " % des variantes volontairement fausses attrapées" : "non évalué") + (r.pieges.mutants ? " (sur " + r.pieges.mutants + ")" : "") + ".</div>";
      return h;
    }

    // ── le bas : ce qui n'existe pas encore ──────────────────────────────
    function bas() {
      return '<details><summary>Dans la maquette, pas encore construit (' + NON_CONSTRUIT.length + ")</summary><ul style=\"margin:8px 0 0 18px;padding:0\">" + NON_CONSTRUIT.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>" +
        '<div class="ev-note" style="margin-top:8px">Ces éléments figurent dans la maquette de conception ; cet écran ne les simule pas.</div></details>';
    }

    function dessiner() {
      if (S.erreur && !S.etat) { racine.innerHTML = '<div class="ev-verdict bad">' + esc(S.erreur) + '</div><div class="ev-note">' + (/fetch|network|réseau/i.test(S.erreur) ? "Le serveur ne répond pas pour l'instant : réessaie dans un instant." : "Le module Évolution est-il actif ? (Réglages › Modules)") + '</div><div class="ev-ligne"><button class="ev-btn" data-geste="actualiser">Réessayer</button></div>';
        racine.querySelectorAll("[data-geste]").forEach((b) => b.addEventListener("click", () => geste(b.dataset.geste)));
        return; }
      racine.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><div class="ev-note">Le moteur de recherche ne fait que proposer du texte ; le noyau juge, écrit, met en ombre et fait monter par paliers.</div>' +
        '<button class="ev-btn" data-geste="actualiser">Actualiser</button></div>' + bandeau() + '<div class="ev-cols"><div>' + rail() + "</div><div>" + centre() + "</div><div>" + gestes() + "</div></div>" + bas();
      racine.querySelectorAll("[data-cible]").forEach((b) => b.addEventListener("click", () => { S.sel = b.dataset.cible; S.resultat = null; S.confirmer = null; dessiner(); }));
      racine.querySelectorAll("[data-onglet]").forEach((b) => b.addEventListener("click", () => { S.onglet = b.dataset.onglet; dessiner(); }));
      racine.querySelectorAll("[data-geste]").forEach((b) => b.addEventListener("click", () => geste(b.dataset.geste)));
    }

    async function geste(nom) {
      if (nom === "annuler") { S.confirmer = null; return dessiner(); }
      if (nom === "actualiser") { await charger(); return dessiner(); }
      if (nom === "proposer" || nom === "retour" || nom === "visiter") { S.confirmer = nom; return dessiner(); }
      const moteur = (racine.querySelector("#ev-moteur") || {}).value || "deterministe", budget = parseInt((racine.querySelector("#ev-budget") || {}).value, 10) || 3;
      S.confirmer = null; S.occupe = true; S.resultat = null; dessiner();
      try {
        if (nom === "proposer-ok") S.resultat = await CASS.agir("evolution.proposer", { point: S.sel, moteur: moteur, budget: budget });
        else if (nom === "retour-ok") S.resultat = await CASS.agir("evolution.retour", { point: S.sel, raison: "retour demandé depuis l'écran" });
        else if (nom === "visiter-ok") S.resultat = await CASS.agir("evolution.visiter", {});
      } catch (e) { S.resultat = { erreur: e.message || String(e) }; }
      S.occupe = false;
      await charger();
      dessiner();
    }

    await charger();
    dessiner();
    const minuteur = setInterval(async () => { if (!document.body.contains(racine)) return clearInterval(minuteur); if (S.occupe || S.confirmer) return; await charger(); dessiner(); }, 20000);
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : l'écran du module Évolution. Il n'appelle que les capacités du module (etat, proposer, retour, visiter) et n'invente aucune donnée.
// EC : néant. Une vue évolutive serait déclarative (jamais du script) : docs/CN_NEXUS.md §5 bis.
// LIEN : modules/evolution (le module), docs/CN_maquette-evolution.html (la maquette), interface/CN_shell.js (le crochet CASS.sceneSurMesure), outils/ui/CN_assembler.py (qui charge ce script).
