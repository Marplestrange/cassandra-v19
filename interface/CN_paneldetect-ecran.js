// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : paneldetect-ecran.js
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #5dce08
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : paneldetect-ecran.js
// MÉTHODE    : une scène (CASS.sceneSurMesure.paneldetect) qui lit paneldetect.etat et seulement elle ; la feuille de style est celle de la maquette validée, portée par .pd.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=5dce08 ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir;
  // La feuille de style : celle de la maquette validée (docs/CN_maquette-panel-detect.html), réduite à ce que la page emploie, portée par .pd.
  const CSS = ".sh-scene:has(>.sh-corps>.pd){width:100%}.pd{color:var(--txt);font:15px/1.5 Inter,system-ui,-apple-system,\"Segoe UI\",sans-serif;padding:6px 4px 48px;max-width:1140px;margin:0 auto}.pd *{box-sizing:border-box}" +
    ".pd .mono{font-family:\"JetBrains Mono\",ui-monospace,Consolas,monospace}.pd button{font:inherit;color:inherit;cursor:pointer}.pd .carte{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);backdrop-filter:blur(18px)}" +
    ".pd .fil{font-size:13px;color:var(--txt-faint);margin:2px 0 6px}.pd h1{font-size:26px;margin:0 0 4px;color:var(--txt-strong,var(--txt));letter-spacing:-.2px}.pd .tete{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}.pd .tete .meta{font-size:13px;color:var(--txt-faint);margin-right:auto;flex:1 1 320px}" +
    ".pd .btn{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:4px 10px;font-size:13px;color:var(--txt-strong,var(--txt))}.pd .btn:hover{border-color:var(--accent)}" +
    ".pd .sec{padding:16px 18px;margin-bottom:16px}.pd .sec h2{font-size:16px;margin:0;color:var(--txt-strong,var(--txt))}.pd .sh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px}.pd .sh .meta{font-size:12.5px;color:var(--txt-faint)}.pd .sh .dr{margin-left:auto;display:flex;gap:6px;align-items:center}" +
    ".pd .verdict{display:flex;gap:14px;align-items:stretch}.pd .vm{width:5px;border-radius:4px;background:var(--ok);flex:none}.pd .vm.w{background:var(--warn)}.pd .vm.d{background:var(--danger)}.pd .vm.n{background:var(--line-strong,var(--line))}.pd .verdict p{margin:0}.pd .vt{font-size:19px;font-weight:700;color:var(--txt-strong,var(--txt))}.pd .vs{color:var(--txt-soft);font-size:14px;margin-top:2px!important}" +
    ".pd .pl{display:inline-flex;align-items:center;gap:5px;font-size:12px;border-radius:999px;padding:2px 9px;background:var(--line);color:var(--txt-soft);white-space:nowrap}.pd .pl::before{content:\"\";width:6px;height:6px;border-radius:50%;background:currentColor}.pd .pl.ok{background:color-mix(in srgb,var(--ok) 12%,transparent);color:var(--ok)}.pd .pl.w{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.pd .pl.i{background:color-mix(in srgb,var(--info,var(--accent)) 12%,transparent);color:var(--info,var(--accent))}" +
    ".pd .rows{display:grid;gap:6px}.pd .row{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1.5fr) auto;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:9px 13px}.pd .row .nm{min-width:0}.pd .row .nm b{display:block;color:var(--txt-strong,var(--txt));font-weight:650}.pd .row .nm small{color:var(--txt-faint);font-size:12.5px;display:block}.pd .row .mil{font-size:13px;color:var(--txt-soft);min-width:0;overflow-wrap:anywhere}.pd .row .cote{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}" +
    "@media (max-width:760px){.pd .row{grid-template-columns:1fr}.pd .row .cote{justify-content:flex-start}}.pd .pv{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px}.pd .pv .ok{color:var(--ok);font-weight:700}.pd .pv .ko{color:var(--txt-faint)}.pd .pv small{color:var(--txt-faint);font-size:12.5px;display:block;overflow-wrap:anywhere}" +
    ".pd .note{font-size:12.5px;color:var(--txt-faint);margin:10px 0 0}.pd .vide{color:var(--txt-faint);font-size:14px;padding:6px 0}.pd .err{color:var(--danger)}";
  const PILULE = { pilote: ["", "pilote"], aucun: ["n", "aucun panneau"], deux: ["d", "deux panneaux"], sans_module: ["w", "sans module"] };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.paneldetect = async function (corps) {
    K.injecter();
    if (!document.getElementById("pd-css")) { const st = document.createElement("style"); st.id = "pd-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "pd"; corps.appendChild(racine);
    const S = { e: null, erreur: "", lu: 0 };
    const pill = (t, c) => '<span class="pl ' + (c || "") + '">' + esc(t) + "</span>";
    const sec = (titre, meta, corpsHtml, droite) => '<section class="carte sec"><div class="sh"><h2>' + titre + '</h2><span class="meta">' + meta + '</span><span class="dr">' + (droite || "") + "</span></div>" + corpsHtml + "</section>";
    const ligne = (nm, sous, mil, cote) => '<div class="row"><div class="nm"><b>' + nm + "</b><small>" + sous + '</small></div><div class="mil">' + mil + '</div><div class="cote">' + cote + "</div></div>";

    function verdict(e) {
      const p = e.panneaux || [], un = p[0] || {};
      let marque, titre, sous;
      if (e.situation === "pilote") { marque = ""; titre = e.nom + " détecté, piloté par son module"; sous = "Preuves : " + (un.preuves || []).join(" · ") + ". Vérifié à chaque lecture de cette page. Si un jour la machine porte un autre panneau, son module prend la place, et les modules ci-dessous n’en savent rien."; }
      else if (e.situation === "deux") { marque = "d"; titre = "Deux panneaux sur la machine : " + p.map((x) => x.nom).join(" et "); sous = "Ils écrivent tous deux la configuration du serveur web et de PHP : l’un peut défaire l’autre. Aucun n’est piloté tant qu’un seul ne reste."; }
      else if (e.situation === "sans_module") { marque = "w"; titre = e.nom + " détecté, sans module de Cassandra pour le piloter"; sous = "Preuves : " + (un.preuves || []).join(" · ") + ". Cassandra lit la machine telle quelle et n’agit pas à la place du panneau."; }
      else { marque = "n"; titre = "Aucun panneau d’hébergement sur cette machine"; sous = "Cassandra ne pose pas de panneau : elle pilote celui qui est là. Le bon ordre est d’installer le panneau d’abord, puis Cassandra. Sans panneau, Sites, Certificats, Sauvegardes et Sécurité font avec ce que Cassandra sait faire seule."; }
      return '<section class="carte sec"><div class="verdict"><span class="vm ' + marque + '"></span><div style="flex:1"><p class="vt">' + esc(titre) + '</p><p class="vs">' + esc(sous) + "</p></div></div></section>";
    }
    function routes(e) {
      const R = e.routes || [], servies = R.filter((r) => r.capacite).length;
      const lignes = R.map((r) => ligne(esc(r.libelle), "demandée par " + esc(r.demandee_par), r.capacite ? '<span class="mono">' + esc(r.capacite) + "</span>" : "", r.capacite ? pill(r.nature === "geste" ? "geste · par " + e.nom : "lecture · par " + e.nom, r.nature === "geste" ? "i" : "ok") : pill("personne", ""))).join("");
      return sec("Qui passe par lui", servies + " fonction" + (servies > 1 ? "s" : "") + " servie" + (servies > 1 ? "s" : "") + " sur " + R.length,
        '<div class="rows">' + lignes + '</div><p class="note">Les lectures passent par Panel Detect ; un geste s’appelle directement, au nom de la personne et avec sa confirmation : Panel Detect dit seulement quelle capacité l’accomplit.</p>');
    }
    function catalogue(e) {
      const S2 = e.signatures || [], ici = new Set((e.panneaux || []).map((p) => p.id));
      return sec("Le catalogue des modules de panneau", "il grandit avec le temps", '<div class="rows">' + S2.map((s) => ligne("Module " + esc(s.nom) + (ici.has(s.id) ? " " + pill("sur cette machine", "i") : ""), s.module ? "installé" : "pas encore écrit", "", s.module ? pill("installé", "ok") : pill("aucun module", ""))).join("") + "</div>");
    }
    function preuves(e) {
      const ici = {}; (e.panneaux || []).forEach((p) => { ici[p.id] = p; });
      return sec("Les preuves", (e.signatures || []).length + " signatures cherchées à chaque lecture", (e.signatures || []).map((s) => {
        const p = ici[s.id];
        return '<div class="pv"><span class="' + (p ? "ok" : "ko") + '">' + (p ? "✓" : "·") + "</span><div><b>" + esc(s.nom) + "</b><small>" + esc(p ? p.preuves.join(" · ") : s.chemins.concat(s.commandes.map((c) => "commande " + c)).join(" · ")) + "</small></div><span></span></div>";
      }).join(""), '<button class="btn" data-a="relire">Refaire la détection</button>');
    }
    function dessiner() {
      const e = S.e;
      const tete = '<p class="fil">Paramètres › Panel Detect</p><div class="tete"><h1>Panel Detect</h1><span class="meta">il se voit peu : il relie chaque module de Cassandra au panneau d’hébergement</span>' + (e ? pill((PILULE[e.situation] || PILULE.aucun)[1], (PILULE[e.situation] || PILULE.aucun)[0]) : "") + "</div>";
      if (S.erreur) { racine.innerHTML = tete + '<section class="carte sec"><p class="err">' + esc(S.erreur) + "</p></section>"; return; }
      if (!e) { racine.innerHTML = tete + '<section class="carte sec"><p class="vide">Lecture…</p></section>'; return; }
      racine.innerHTML = tete + verdict(e) + routes(e) +
        sec("Opérations du panneau", "ce qu’aucun autre module ne fait · réservé à l’administrateur", '<p class="note" style="margin:0">L’onglet Hébergement est retiré : ces opérations (services du panneau, crons, analyses par site, lancement d’un plan de sauvegarde) restent servies par le module du panneau, mais n’ont pas encore d’écran ; elles viendront ici.</p>') +
        catalogue(e) + preuves(e) +
        sec("Sans panneau", "", '<p class="note" style="margin:0">Le guide d’installation le dit : d’abord le panneau, ensuite Cassandra. Sans panneau, Bases de données et Gestion e-mail ne sont pas dans le menu ; Sites, Certificats, Sauvegardes et Sécurité font avec ce que Cassandra sait faire seule.</p>');
    }
    async function lire() {
      try { S.e = await agir("paneldetect.etat", {}); S.erreur = ""; } catch (err) { S.erreur = (err && err.message) || String(err); }
      S.lu = Date.now(); dessiner();
    }
    racine.addEventListener("click", (ev) => { const a = ev.target.closest("[data-a]"); if (a && a.dataset.a === "relire") lire(); });
    const onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active"); new MutationObserver(() => { const actif = onglet.classList.contains("active"); if (actif && !etait) lire(); etait = actif; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    dessiner(); await lire();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : modules/paneldetect ; docs/CN_maquette-panel-detect.html ; interface/CN_index.html et outils/ui/CN_assembler.py (le script est servi)
