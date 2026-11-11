// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La machine : la page du Panorama qui remplace le tiroir « Détails système » (maquette : do
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #00dff4
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La machine : la page du Panorama qui remplace le tiroir « Détails système » (maquette : docs/CN_maquette-systeme.html).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=00dff4 ▼▼▼
// La machine : la page du Panorama qui remplace le tiroir « Détails système » (maquette : docs/CN_maquette-systeme.html).
// Une seule page où tout se voit d'un coup d'œil, une tuile par sujet ; le détail d'un sujet s'ouvre au clic, « ‹ La machine » y ramène.
// Tout vient d'UNE lecture, vue.machine, qui compose ce que les modules relèvent déjà ; les ressources et les processus se relisent seuls
// toutes les cinq secondes (sensorium.metriques), le reste chaque minute. Rien n'est inventé : une source muette dit « inconnu ».
// Lot 1 : ce qui se lit déjà, et les gestes qui existent (acquitter, réinitialiser, déconnecter, relancer et lire les quatre services de la maison).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir, dire = K.dire;
  const CSS = "#tab-overview[data-vue=\"machine\"]>:not(#mc19){display:none!important}#tab-overview:not([data-vue=\"machine\"])>#mc19{display:none}.mc{color:var(--txt);font:15px/1.5 Inter,system-ui,-apple-system,\"Segoe UI\",sans-serif;padding:6px 4px 48px;max-width:1140px;margin:0 auto}.mc *{box-sizing:border-box}.mc a{cursor:pointer;color:var(--accent)}.mc h2,.mc h3{margin:0}.mc .tu:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.mc .mono,.mc code,.mc .num{font-family:\"JetBrains Mono\",ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}.mc code{font-size:.92em;color:var(--txt-strong,var(--txt))}.mc button{font:inherit;color:inherit;cursor:pointer}.mc :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:8px}.mc svg.i{width:17px;height:17px;flex:none;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.mc .carte{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);backdrop-filter:blur(18px)}.mc .fil{font-size:13px;color:var(--txt-faint);margin:2px 0 6px}.mc h1{font-size:26px;margin:0 0 4px;color:var(--txt-strong,var(--txt));letter-spacing:-.2px}.mc .tete{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}.mc .tete .meta{font-size:13px;color:var(--txt-faint);margin-right:auto;flex:1 1 320px}.mc .btn{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:7px 13px;font-size:14px;color:var(--txt-strong,var(--txt));display:inline-flex;align-items:center;gap:7px}.mc .btn:hover{border-color:var(--accent)}.mc .btn.p{background:var(--accent);border-color:var(--accent);color:#fff}:root[data-theme=\"dark\"] .mc .btn.p{color:#06231f}.mc .btn.d{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 12%,transparent)}.mc .btn:disabled{opacity:.5;cursor:not-allowed}.mc .btn.s{padding:4px 10px;font-size:13px}.mc .sec{padding:16px 18px;margin-bottom:16px}.mc .sec h2{font-size:16px;margin:0;color:var(--txt-strong,var(--txt))}.mc .sh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px}.mc .sh .meta{font-size:12.5px;color:var(--txt-faint)}.mc .sh .dr{margin-left:auto;display:flex;gap:6px;align-items:center}.mc .cmd{background:transparent;border:0;color:var(--txt-faint);border-radius:8px;padding:2px 7px;font-size:14px}.mc .cmd:hover{background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--txt-strong,var(--txt))}.mc .sec.plie>:not(.sh){display:none}.mc .sec.plie .sh{margin-bottom:0}.mc .sec.plein{position:fixed;inset:14px;z-index:9000;overflow:auto;margin:0;background:var(--surface-solid,var(--surface))}.mc .age{font-size:12px;color:var(--txt-faint);display:inline-flex;align-items:center;gap:6px}.mc .age::before{content:\"\";width:7px;height:7px;border-radius:50%;background:var(--ok)}.mc .age.mu::before{background:var(--danger)}.mc .age.mu{color:var(--danger)}.mc .verdict{display:flex;gap:14px;align-items:stretch}.mc .vm{width:5px;border-radius:4px;background:var(--ok);flex:none}.mc .vm.w{background:var(--warn)}.mc .vm.d{background:var(--danger)}.mc .vm.n{background:var(--line-strong,var(--line))}.mc .verdict p{margin:0}.mc .vt{font-size:19px;font-weight:700;color:var(--txt-strong,var(--txt))}.mc .vs{color:var(--txt-soft);font-size:14px;margin-top:2px!important}.mc .gestes{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.mc .jauges{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.mc .jg{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:11px 13px}.mc .jg span{display:block;font-size:12.5px;color:var(--txt-faint)}.mc .jg b{display:block;font:650 24px/1.2 \"JetBrains Mono\",ui-monospace,monospace;color:var(--txt-strong,var(--txt))}.mc .jg b.w{color:var(--warn)}.mc .jg b.d{color:var(--danger)}.mc .jg b.mu{color:var(--txt-faint)}.mc .jg em{display:block;font-style:normal;font-size:12.5px;color:var(--txt-soft)}.mc .barre{height:5px;border-radius:3px;background:var(--line);margin:7px 0 4px;overflow:hidden}.mc .barre i{display:block;height:100%;border-radius:3px;background:var(--accent);transition:width .6s}.mc .barre i.w{background:var(--warn)}.mc .barre i.d{background:var(--danger)}.mc .courbe{width:100%;height:150px;display:block}.mc .leg{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--txt-faint);margin-top:8px}.mc .leg i{display:inline-block;width:10px;height:3px;border-radius:2px;margin-right:5px;vertical-align:3px}.mc .pl{display:inline-flex;align-items:center;gap:5px;font-size:12px;border-radius:999px;padding:2px 9px;background:var(--line);color:var(--txt-soft);white-space:nowrap}.mc .pl::before{content:\"\";width:6px;height:6px;border-radius:50%;background:currentColor}.mc .pl.ok{background:color-mix(in srgb,var(--ok) 12%,transparent);color:var(--ok)}.mc .pl.w{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.mc .pl.d{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger)}.mc .pl.i{background:color-mix(in srgb,var(--info,var(--accent)) 12%,transparent);color:var(--info,var(--accent))}.mc .rows{display:grid;gap:6px}.mc .row{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1.2fr) auto;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:9px 13px}.mc .row .nm{min-width:0}.mc .row .nm b{display:block;color:var(--txt-strong,var(--txt));overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:650}.mc .row .nm small{color:var(--txt-faint);font-size:12.5px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc .row .mil{font-size:13px;color:var(--txt-soft);min-width:0;display:flex;align-items:center;gap:8px}.mc .row .cote{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}@media (max-width:760px){.mc .row{grid-template-columns:1fr}.mc .row .cote{justify-content:flex-start}}.mc .paires{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:2px 26px;margin:0}.mc .paires div{display:flex;gap:10px;padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px;align-items:baseline}.mc .paires dt{color:var(--txt-faint);flex:0 0 118px;font-size:13px}.mc .paires dd{margin:0;color:var(--txt-strong,var(--txt));min-width:0}.mc .paires dd small{display:block;color:var(--txt-soft);font-size:12.5px}.mc .vide{color:var(--txt-faint);font-size:14px;padding:6px 0}.mc .muet{background:color-mix(in srgb,var(--danger) 12%,transparent);border:1px solid var(--line);border-radius:13px;padding:11px 14px;font-size:14px;color:var(--txt-strong,var(--txt))}.mc .note{font-size:12.5px;color:var(--txt-faint);margin-top:10px}.mc input[type=search]{font:inherit;color:var(--txt-strong,var(--txt));background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:6px 11px;min-width:0;width:220px}.mc .pbar{flex:1;height:5px;border-radius:3px;background:var(--line);overflow:hidden;min-width:60px}.mc .pbar i{display:block;height:100%;background:var(--accent)}.mc .pbar i.w{background:var(--warn)}.mc .pbar i.d{background:var(--danger)}.mc .puces{display:flex;gap:6px;flex-wrap:wrap}.mc .puce{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:3px 9px;font-size:12.5px;color:var(--txt-strong,var(--txt))}.mc .puce:hover{border-color:var(--accent)}.mc .bandeau-v{padding:14px 18px;margin-bottom:6px}.mc .bandeau-v .vt{font-size:18px}.mc .note-sante{text-align:right;min-width:150px;cursor:help}.mc .note-sante span,.mc .note-sante em{display:block;font-size:12.5px;color:var(--txt-faint);font-style:normal}.mc .note-sante b{display:block;font-size:28px;line-height:1.1}.mc .note-sante b small{font-size:13px;color:var(--txt-faint)}.mc .gt{font-size:11px;letter-spacing:.9px;text-transform:uppercase;color:var(--txt-faint);margin:14px 4px 8px;font-weight:650;display:flex;align-items:center;gap:8px;min-height:26px}.mc .gt .btn{margin-left:auto;text-transform:none;letter-spacing:0}.mc .gt span{text-transform:none;letter-spacing:0;font-weight:500}.mc .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:10px}.mc .tu{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 13px 10px;display:flex;flex-direction:column;gap:5px;cursor:pointer;box-shadow:var(--shadow-glass);min-height:158px;min-width:0}.mc .tu:hover{border-color:var(--accent);background:var(--surface-solid,var(--surface))}.mc .tu.ext{background:var(--surface);box-shadow:none}.mc .tu.mu>:not(.tt):not(.tp){opacity:.42;filter:grayscale(1)}.mc .tu .tt{display:flex;align-items:center;gap:8px;color:var(--txt-strong,var(--txt));font-size:14px;margin-bottom:2px}.mc .tu .tt b{font-weight:650}.mc .tu .tt .pl{margin-left:auto}.mc .tu .gr{font:650 25px/1.1 \"JetBrains Mono\",ui-monospace,monospace;color:var(--txt-strong,var(--txt))}.mc .tu .gr.w{color:var(--warn)}.mc .tu .gr.d{color:var(--danger)}.mc .tu .gr.mu{color:var(--txt-faint)}.mc .tu .cc{display:flex;flex-direction:column;gap:5px}.mc .tu .li{font-size:12.5px;color:var(--txt-soft);display:flex;gap:8px;align-items:center;min-width:0}.mc .tu .li .n{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc .tu .li small{color:var(--txt-faint)}.mc .tu .li b{color:var(--txt-strong,var(--txt));font-weight:600;font-size:12px;white-space:nowrap}.mc .tu .mb{display:grid;grid-template-columns:74px 1fr 42px;gap:8px;align-items:center;font-size:12.5px;color:var(--txt-soft)}.mc .tu .mb b{text-align:right;font-size:12px}.mc .tu .tp{margin-top:auto;padding-top:5px;font-size:12px;font-weight:600;color:var(--accent)}.mc .tu.ext .tp{color:var(--txt-faint)}.mc .tu .puces{margin-top:2px}.mc .tu .puce{padding:2px 7px;font-size:12px}.mc .tu .btn.s{padding:2px 8px;font-size:12px}.mc .grille.v{grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:8px}.mc .grille.v .tu{min-height:124px;padding:10px 10px 8px}.mc .grille.v .tu .gr{font-size:21px}.mc .grille.v .tu .tt{font-size:13px;flex-wrap:wrap;gap:6px}.mc .grille.v .tu .tt svg.i{width:15px;height:15px}.mc .grille.v .tu .tt .pl{font-size:11px;padding:1px 7px}.mc .grille.v .tu .li{flex-wrap:wrap}.mc .grille.v .tu .li .n{white-space:normal}.mc .duo{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:16px;margin-bottom:16px;align-items:start}@media (max-width:560px){.mc .duo{grid-template-columns:1fr}}.mc .duo .paires.un dt{flex-basis:118px}.mc .cass{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;background:color-mix(in srgb,var(--accent) 10%,transparent);border:1px solid color-mix(in srgb,var(--accent) 22%,transparent);border-radius:12px;padding:4px 8px 4px 10px;font-size:13px;color:var(--accent)}.mc .cass b{font-weight:650;margin-right:2px}.mc .cass .puce{font-size:12.5px;padding:3px 9px}.mc .chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.mc .chip{background:transparent;border:1px solid var(--line-strong,var(--line));border-radius:999px;padding:3px 11px;font-size:13px;color:var(--txt-soft)}.mc .chip[aria-pressed=\"true\"]{background:var(--accent);border-color:var(--accent);color:#fff}:root[data-theme=\"dark\"] .mc .chip[aria-pressed=\"true\"]{color:#06231f}.mc .plan{margin:0 0 12px;padding-left:22px;font-size:14px;color:var(--txt-strong,var(--txt));display:grid;gap:6px}.mc .pile{display:flex;height:16px;border-radius:8px;overflow:hidden;background:var(--line);gap:2px}.mc .pile i{display:block;height:100%}.mc .dit{margin:0 0 4px;font-size:14px;color:var(--txt)}.mc pre.jl{margin:0;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 10px;font:11.5px/1.5 \"JetBrains Mono\",ui-monospace,monospace;color:var(--txt);white-space:pre-wrap;word-break:break-word}.mc .cts{display:grid;gap:6px}.mc .ct{background:var(--surface);border:1px solid var(--line);border-radius:13px;overflow:hidden}.mc .ct.ouvert{border-color:color-mix(in srgb,var(--accent) 22%,transparent);background:var(--surface-solid,var(--surface))}.mc .ctl{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1.25fr) minmax(0,1.15fr) 200px 14px;gap:14px;align-items:center;width:100%;text-align:left;background:transparent;border:0;padding:10px 13px}.mc .ctl:hover{background:color-mix(in srgb,var(--accent) 10%,transparent)}.mc .ctl>span{min-width:0;display:flex;flex-direction:column;gap:2px}.mc .ctl b,.mc .ctl .mono{color:var(--txt-strong,var(--txt));overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13.5px}.mc .ctl b{font-weight:650;font-size:14.5px}.mc .ctl small{color:var(--txt-faint);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc .ctl .c3{flex-direction:row;flex-wrap:wrap;gap:4px 6px;align-items:center}.mc .ctl .c3 small{flex:1 1 100%}.mc .ctl .c4{align-items:flex-end}.mc .ctl .chev{color:var(--txt-faint);transition:transform .2s}.mc .ct.ouvert .ctl .chev{transform:rotate(90deg)}.mc .pc{font:600 12px \"JetBrains Mono\",ui-monospace,monospace;border:1px solid var(--line-strong,var(--line));border-radius:7px;padding:1px 6px;color:var(--txt-strong,var(--txt));background:var(--surface-solid,var(--surface))}.mc .pc.w{border-color:var(--warn);color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}.mc .ctf{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:4px 26px;padding:6px 16px 14px;border-top:1px solid var(--line)}.mc .ctf .bloc{min-width:0;padding-top:8px}.mc .ctf h3{font-size:11px;letter-spacing:.8px;text-transform:uppercase;color:var(--txt-faint);margin:0 0 4px;font-weight:650}.mc .ctf h3 .ac{text-transform:uppercase}.mc .ctf table.ptab{font-size:13px}.mc .ctf table.ptab th{font-size:11px;padding:4px 6px}.mc .ctf table.ptab td{padding:5px 6px;font-weight:500;color:var(--txt);white-space:nowrap}.mc .ctf table.ptab td:first-child{font-weight:500}.mc .paires.un{grid-template-columns:1fr}.mc .paires.un div{padding:5px 0;font-size:13.5px}.mc .paires.un dt{flex-basis:104px}.mc .paires.un dd small{display:inline;margin-left:4px}.mc .ctf a,.mc .note a{color:var(--accent);cursor:pointer}@media (max-width:860px){.mc .ctl{grid-template-columns:1fr}.mc .ctl .c4{align-items:flex-start}.mc .ctl .chev{display:none}}.mc .lk{cursor:pointer;background:none;border:0;padding:0;color:var(--txt-soft);font-size:12.5px;text-decoration:underline dotted;text-underline-offset:3px}.mc .lk:hover{color:var(--accent)}.mc .pt{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:4px}.mc .pt.d{background:var(--danger)}.mc .pied{font-size:13px;color:var(--txt-faint);margin:14px 4px 0}.mc .pied a,.mc .fil a{color:var(--accent);cursor:pointer}.mc .grille.v{grid-template-columns:repeat(auto-fit,minmax(128px,1fr))}.mc .grille.v .tu .tt{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:4px 6px}.mc .ctl.large .nm{grid-column:1/4}.mc .ctl.large .c2,.mc .ctl.large .c3{display:none}.mc .grille.v .tu{container-type:inline-size}@container (max-width:117px){.mc .grille.v .tu .tt{display:block}.mc .grille.v .tu .tt svg.i{display:none}.mc .grille.v .tu .tt .pl{display:inline-flex;margin-top:4px}}.mc .grille.v .tu .tt .pl{grid-column:1/-1;justify-self:start;margin-left:0}.mc .sec>.paires.un dt{flex-basis:160px}";
  // l'état vit hors de la page : elle se redessine à chaque relève
  const S = { page: "vue", d: null, erreur: "", charge: false, q: "", groupe: false, sv: "", svF: "tous", svQ: "", ct: "", pr: "", se: "", hist: { cpu: [], ram: [] }, minuteurs: [], lu: 0 };
  let R = null;
  const IC = {
    machine: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>', direct: '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
    proc: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    services: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    conteneurs: '<path d="M12 3l9 5v8l-9 5-9-5V8z"/><path d="M3 8l9 5 9-5M12 13v8"/>', ailleurs: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>', bouclier: '<path d="M12 3l8 3v6c0 4.500-3.200 7.600-8 9-4.800-1.400-8-4.500-8-9V6z"/>',
    base: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.700 3.600 3 8 3s8-1.300 8-3V6M4 12c0 1.700 3.600 3 8 3s8-1.300 8-3"/>', bulle: '<path d="M4 5h16v11H9l-5 4z"/>',
  };
  const ico = (k) => '<svg class="i" viewBox="0 0 24 24" aria-hidden="true">' + (IC[k] || "") + "</svg>";
  const fr = (v, d) => (v == null || isNaN(v) ? "—" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d == null ? 1 : d }));
  const niv = (v) => (v >= 90 ? "d" : v >= 75 ? "w" : "");
  const pill = (t, c) => '<span class="pl ' + (c || "") + '">' + esc(t) + "</span>";
  const D = () => S.d || {};
  const muet = () => !S.d || (S.d.source && S.d.source.muet);
  const duree = (s) => (s >= 7200 ? Math.floor(s / 3600) + " h" : s >= 120 ? Math.floor(s / 60) + " min" : s + " s");
  // L'âge de ce qu'on montre : la source et depuis quand. Des relevés figés ou un collecteur muet se disent en rouge.
  function age() {
    const so = D().source || {};
    if (!S.d) return '<span class="age mu">' + esc(S.erreur || "lecture en cours…") + "</span>";
    if (so.muet) return '<span class="age mu">le collecteur ne répond pas</span>';
    if (so.fige) return '<span class="age mu">relevés figés depuis ' + esc(duree(so.age_s || 0)) + "</span>";
    return '<span class="age">collecteur · il y a ' + esc(duree((so.age_s || 0) + Math.round((Date.now() - S.lu) / 1000))) + "</span>";
  }
  // Chaque bloc porte les commandes communes : plein écran et repli.
  const sec = (titre, meta, corps, droite) => '<section class="carte sec"><div class="sh"><h2>' + titre + '</h2><span class="meta">' + (meta || "") + '</span><span class="dr">' + (droite || "") +
    '<button class="cmd" title="Plein écran — Échap pour revenir" aria-label="Plein écran" data-a="plein">⤢</button><button class="cmd" title="Replier ce bloc" aria-label="Replier" data-a="plier">▾</button></span></div>' + corps + "</section>";
  const inconnu = (quoi) => '<div class="muet"><b>' + esc(quoi) + " : inconnu.</b> Le collecteur du Sensorium n’a pas répondu. Rien n’est affiché à la place — ni zéro, ni « aucun ». " +
    '<button class="btn s" style="margin-left:8px" data-a="svc" data-g="collecteur">Redémarrer le collecteur</button></div>';
  // L'appel à Cassandra : des questions prêtes, posées avec le contexte de la ligne ouverte.
  const cass = (qs) => '<span class="cass">' + ico("bulle") + "<b>Cassandra</b>" + qs.map((q) => '<button class="puce" data-a="demander" data-q="' + esc(q[1]) + '">' + esc(q[0]) + "</button>").join("") + "</span>";
  const demande = (libelle, q, cls) => '<button class="btn s ' + (cls || "") + '" data-a="demander" data-q="' + esc(q) + '">' + ico("bulle") + esc(libelle) + "</button>";
  const tete = (titre, meta, droite) => '<p class="fil"><a data-a="page" data-p="vue">La machine</a> › ' + esc(titre) + '</p><div class="tete"><button class="btn s" data-a="page" data-p="vue" title="Revenir à la page d’ensemble">‹ La machine</button><h1>' +
    esc(titre) + '</h1><span class="meta">' + (meta || "") + "</span>" + (droite || "") + "</div>";
  const court = (commande) => (String(commande).split(" ")[0].split("/").pop() || String(commande)).replace(/:$/, "");

  // ───────────────────────── la page d'ensemble : une tuile par sujet
  function tuile(id, ic, titre, etat, corps, ou, action) {
    return '<div class="tu ' + (ou ? "ext" : "") + '" role="link" tabindex="0" ' + action + '><span class="tt">' + ico(ic) + "<b>" + esc(titre) + "</b>" + (etat ? pill(etat[0], etat[1]) : "") + "</span>" + corps +
      '<span class="tp">' + (ou ? "↗ " + esc(ou) : "Détail ›") + "</span></div>";
  }
  const gr = (v, c) => '<span class="gr ' + (c || "") + '">' + v + "</span>";
  const li = (g, d, c) => '<span class="li"><span class="n">' + g + "</span>" + (d ? '<b class="num"' + (c ? ' style="color:var(--' + c + ')"' : "") + ">" + d + "</b>" : "") + "</span>";
  const mb = (nom, pct, val) => '<span class="mb"><span>' + nom + '</span><span class="pbar"><i class="' + niv(pct) + '" style="width:' + Math.min(pct || 0, 100) + '%"></i></span><b class="num" style="color:var(--' + (pct >= 90 ? "danger" : pct >= 75 ? "warn" : "txt-strong") + ')">' + val + "</b></span>";
  const tuileInconnue = (id, ic, titre, page) => tuile(id, ic, titre, ["inconnu", ""], gr("—", "mu") + li("le collecteur n’a pas répondu"), "", 'data-a="page" data-p="' + page + '"');
  function corpsRes() {
    const r = D().ressources; if (!r) return gr("—", "mu") + li("mesures indisponibles");
    return mb("Processeur", r.cpu, fr(r.cpu, 0) + " %") + mb("Mémoire", r.ram, fr(r.ram, 0) + " %") + mb("Échange", r.swap, fr(r.swap, 0) + " %") + mb("Disque /", r.disque, fr(r.disque, 0) + " %") +
      li("charge " + r.charge.map((c) => fr(c, 2)).join(" · "));
  }
  function corpsProc() {
    const l = D().processus || []; if (!l.length) return gr("—", "mu") + li("aucun processus relevé");
    return l.slice(0, 4).map((p) => li('<span class="mono">' + esc(court(p.commande)) + "</span> <small>" + esc(p.utilisateur) + "</small>", fr(p.cpu) + " %", p.cpu > 50 ? "danger" : p.cpu > 20 ? "warn" : "")).join("");
  }
  function voisin(v) {
    const act = 'data-a="module" data-e="' + esc(v.aller[0]) + '" data-v="' + esc(v.aller[1] || "") + '" data-ou="' + esc(v.ou) + '"';
    if (v.etat === "detecte" || v.etat === "muet") {
      return '<div class="tu ext" style="border-style:dashed" role="link" tabindex="0" ' + act + '><span class="tt">' + ico("ailleurs") + "<b>" + esc(v.titre) + "</b>" + pill(v.etat === "muet" ? "muet" : "détecté", v.etat === "muet" ? "w" : "i") +
        '</span><span class="li"><span class="n" style="white-space:normal">trouvé sur la machine : ' + esc(v.preuve) + '</span></span><span class="li"><span class="n" style="white-space:normal">' +
        (v.etat === "muet" ? "son module ne répond pas" : "aucun module ne le suit encore") + '</span></span><span class="tp" style="color:var(--accent)">' + (v.etat === "muet" ? "↗ " + esc(v.ou) : "Installer le module ›") + "</span></div>";
    }
    const ic = { ports: "bouclier", bannies: "bouclier", certs: "bouclier", tailscale: "globe", netbird: "bouclier", heberg: "base", depots: "base" }[v.cle] || "ailleurs";
    let corps = gr(esc(v.chiffre == null ? "—" : String(v.chiffre)), v.pastille && v.pastille[1] === "w" && v.cle === "depots" ? "w" : "");
    if (v.cle === "heberg") {
      corps += '<span class="li" style="flex-wrap:wrap;gap:2px 8px">' + Object.keys(v.details).filter((k) => v.details[k] != null).map((k) => '<button class="lk" data-a="module" data-e="hebergement" data-v="" data-ou="Hébergement › ' + esc(k) + '">' + esc(k) + " <b>" + esc(v.details[k]) + "</b></button>").join("") + "</span>";
    } else corps += v.lignes.map((l) => li(esc(l))).join("");
    if (v.cle === "certs") corps += '<span class="li"><button class="btn s" data-a="demander" data-q="Certificats SSL expirants ?">Demander</button></span>';
    return tuile(v.cle, ic, v.titre, v.pastille, corps, v.ou, act);
  }
  const PAGES = {
    vue() {
      const d = D(), m = d.machine || {}, so = d.source || {}, sa = d.sante || {}, cl = d.cloche || [], mu = muet();
      const pire = cl[0], c = mu ? "n" : so.fige ? "d" : pire ? (pire.gravite === "critique" || /^prevision|^montage|^service/.test(pire.cle) ? "d" : "w") : "";
      const titre = !S.d ? "Lecture de la machine…" : mu ? "La machine est inconnue : le collecteur ne répond pas" : so.fige ? "Les relevés sont figés depuis " + duree(so.age_s || 0) : pire ? (pire.phrase || pire.titre + " : " + pire.texte) : "Rien ne cloche sur la machine";
      const sous = !S.d ? "" : mu ? "Aucune tuile ne passe à zéro ni n’écrit « tout va bien » : chacune dit « inconnu »." : so.fige ? "Le collecteur répond, mais ne mesure plus : tout ce que la page montre date d’autant. Cassandra le relance d’elle-même." :
        pire ? (cl.length > 1 ? "Et " + (cl.length - 1) + " autre" + (cl.length > 2 ? "s points" : " point") + " : " + cl.slice(1, 4).map((x) => { const t = x.phrase || x.titre; return t.charAt(0).toLowerCase() + t.slice(1); }).join(" ; ") + (cl.length > 4 ? "…" : "") + "." : "Rien d’autre ne cloche.") :
          "Aucune mesure en alerte.";
      const gestes = !S.d ? "" : mu || so.fige ? '<button class="btn s p" data-a="svc" data-g="collecteur">Redémarrer le collecteur</button><button class="btn s" data-a="module" data-e="sensorium" data-v="demon" data-ou="Sensorium › Le démon">Le démon du Sensorium</button>' :
        (pire && /disque|montage/.test(pire.cle) ? '<button class="btn s p" data-a="page" data-p="ressources">Voir le disque</button>' + demande("Qu’est-ce qui le remplit ?", "Qu’est-ce qui remplit le disque de la machine " + (m.nom || "") + " ?") : "") +
        (((d.services || {}).echecs || []).length ? '<button class="btn s p" data-a="page" data-p="services">' + (d.services.echecs.length > 1 ? "Les " + d.services.echecs.length + " unités en échec" : "L’unité en échec") + "</button>" : "") +
        (m.redemarrage ? pill("redémarrage requis", "d") : "") + '<button class="btn s" data-a="module" data-e="sensorium" data-v="maintenant" data-ou="Sensorium › Maintenant">Les ' + (sa.alertes || 0) + " alertes du Sensorium</button>";
      let h = '<div class="tete"><h1>La machine</h1><span class="meta">' + (m.nom ? '<b style="color:var(--txt-strong,var(--txt))">' + esc(m.nom) + "</b> · " + esc([m.os, m.archi, m.nature].filter(Boolean).join(" · ")) + (m.allumee ? " · allumée depuis " + esc(m.allumee) : "") : "") +
        "</span>" + age() + '<button class="btn" data-a="relever">Relever</button>' + demande("Demander à Cassandra", "Fais-moi le point sur la machine " + (m.nom || "") + ".", "").replace("btn s ", "btn ") + "</div>";
      h += '<section class="carte sec bandeau-v"><div class="verdict"><div class="vm ' + c + '"></div><div style="flex:1;min-width:0"><p class="vt">' + esc(titre) + '</p><p class="vs">' + esc(sous) + '</p><div class="gestes">' + gestes + "</div></div>" +
        (sa.score == null ? "" : '<div class="note-sante" title="La note d’ensemble du Sensorium. L’ancien écran affichait ' + esc(sa.ressources) + ' : la note des ressources seules."><span>Santé</span><b class="num" style="color:var(--' + (sa.score < 50 ? "danger" : sa.score < 80 ? "warn" : "ok") + ')">' + sa.score + "<small> /100</small></b><em>" + esc(sa.mot) + (sa.ressources != null ? " · ressources " + esc(sa.ressources) : "") + "</em></div>") + "</div></section>";
      if (!S.d) return h;
      const d0 = (d.disques || [])[0], sv = d.services, ct = d.conteneurs, se = d.sessions, oom = d.oom;
      h += '<h2 class="gt">Sur cette machine <span>un clic ouvre le détail</span></h2><div class="grille">';
      h += tuile("res", "direct", "Ressources", null, '<span id="mc-res" class="cc">' + corpsRes() + "</span>", "", 'data-a="page" data-p="ressources"');
      h += d0 && d0.pct != null ? tuile("disque", "base", "Disque", [d0.alerte ? "à regarder" : "stable", d0.alerte ? "d" : "ok"], gr(d0.pct + " %", niv(d0.pct)) + li(fr(d0.utilise_go, 0) + " sur " + fr(d0.total_go, 0) + " Go · " + fr(d0.total_go - d0.utilise_go, 0) + " Go libres") +
        li('<span style="color:var(--' + (d0.alerte ? "danger" : "txt-soft") + ')">' + esc(d0.prevision.split(" (")[0]) + "</span>"), "", 'data-a="page" data-p="ressources"') : tuileInconnue("disque", "base", "Disque", "ressources");
      h += tuile("proc", "proc", "Processus", null, '<span id="mc-proc" class="cc">' + corpsProc() + "</span>", "", 'data-a="page" data-p="proc"');
      h += oom == null ? tuileInconnue("oom", "proc", "Mémoire saturée", "proc") : tuile("oom", "proc", "Mémoire saturée", oom.length ? [oom.length + (oom.length > 1 ? " tués" : " tué"), "d"] : ["aucun", "ok"], gr(oom.length, oom.length ? "d" : "") +
        (oom.length ? oom.slice(0, 2).map((o) => li('<span class="mono">' + esc(o.processus) + "</span>", fr(o.mo / 1024) + " Go")).join("") : li("aucun processus tué faute de mémoire")), "", 'data-a="page" data-p="proc"');
      h += sv == null ? tuileInconnue("services", "services", "Services", "services") : tuile("services", "services", "Services", sv.echecs.length ? [sv.echecs.length + " en échec", "d"] : ["aucun échec", "ok"], gr(sv.echecs.length, sv.echecs.length ? "d" : "") +
        (sv.echecs.length ? sv.echecs.slice(0, 2).map((u) => li('<span class="mono">' + esc(u) + "</span>")).join("") : li("aucune unité en échec")) + li(sv.actifs + " actifs sur " + sv.total), "", 'data-a="page" data-p="services"');
      if (d.docker) {
        const ko = (ct || []).filter((x) => !x.tourne);
        h += ct == null ? tuileInconnue("conteneurs", "conteneurs", "Conteneurs", "conteneurs") : tuile("conteneurs", "conteneurs", "Conteneurs", ko.length ? [ko.length + " arrêté" + (ko.length > 1 ? "s" : ""), "w"] : ["tous tournent", "ok"],
          gr(ct.length - ko.length + " / " + ct.length, ko.length ? "w" : "") + li(ct.map((x) => '<span class="pt ' + (x.tourne ? "ok" : "d") + '"></span>' + esc(x.nom)).join(" &nbsp;")), "", 'data-a="page" data-p="conteneurs"');
      }
      h += se == null ? tuileInconnue("sessions", "bouclier", "Sessions", "sessions") : tuile("sessions", "bouclier", "Sessions", se.length ? [se.length + " ouverte" + (se.length > 1 ? "s" : ""), "i"] : ["aucune", ""],
        se.length ? se.slice(0, 3).map((x, i) => '<span class="li"><span class="n mono">' + esc(x.utilisateur) + " · " + esc(x.adresse) + '</span><button class="btn s d" data-a="deconnecter" data-i="' + i + '">Déconnecter</button></span>').join("") : gr("0") + li("aucune session ouverte"), "", 'data-a="page" data-p="sessions"');
      h += tuile("fiche", "machine", "La fiche", m.redemarrage ? ["redémarrage requis", "d"] : null, li("noyau", esc(m.noyau || "—")) + li("adresse", esc((((m.interfaces || [])[0] || {}).v4 || [])[0] || "—")) +
        li("mises à jour", m.maj && m.maj.total != null ? (m.maj.total ? m.maj.total + (m.maj.secu ? " dont " + m.maj.secu + " de sécurité" : " en attente") : "à jour") : "—", m.maj && m.maj.secu ? "danger" : "") + li("horloge", esc((m.horloge || "—").split(" (")[0])), "", 'data-a="page" data-p="fiche"');
      h += "</div>";
      const vo = d.voisins || [];
      h += '<h2 class="gt">Chez les voisins <span>découverte automatique : ' + vo.length + " trouvé" + (vo.length > 1 ? "s" : "") + ' sur cette machine · un clic mène chez eux</span><button class="btn s" data-a="decouverte">Découverte</button></h2><div class="grille v">' + vo.map(voisin).join("") + "</div>";
      h += '<p class="pied">Les courbes longues : <a data-a="module" data-e="historique" data-v="" data-ou="Historique">Historique →</a> · tous les relevés, les alertes et leurs seuils : <a data-a="module" data-e="sensorium" data-v="maintenant" data-ou="Sensorium">Sensorium →</a> · les autres machines : <a data-a="module" data-e="flotte" data-v="" data-ou="Flotte">Flotte →</a></p>';
      return h;
    },
    ressources() {
      const d = D(), r = d.ressources;
      if (!r) return tete("Ressources", "processeur, mémoire, disques", age()) + inconnu("Les ressources");
      return tete("Ressources", "processeur, mémoire, échange, disques", age()) +
        sec("Ressources", "relues toutes les 5 s", '<div class="jauges" id="mc-jauges">' + jauges() + '</div><svg class="courbe" id="mc-courbe" viewBox="0 0 600 150" preserveAspectRatio="none" role="img" aria-label="Processeur et mémoire sur les cinq dernières minutes"></svg>' +
          '<div class="leg"><span><i style="background:var(--accent)"></i>processeur</span><span><i style="background:var(--violet,#7c5cfc)"></i>mémoire</span><span>depuis l’ouverture de la page · un point toutes les 5 s · de 0 à 100 %</span>' +
          '<a style="margin-left:auto;color:var(--accent);cursor:pointer" data-a="module" data-e="historique" data-v="" data-ou="Historique">Les courbes longues dans Historique →</a></div>') +
        sec("Disques", "place et prévision", '<div class="rows">' + (d.disques || []).map((x) => '<div class="row"><div class="nm"><b class="mono">' + esc(x.montage) + "</b><small>" + (x.type ? esc(x.type) + " · " : "") + fr(x.utilise_go) + " sur " + fr(x.total_go) + " Go" +
          (x.inodes_pct != null ? " · fichiers : " + x.inodes_pct + " % des inodes" : "") + '</small></div><div class="mil"><span class="pbar"><i class="' + niv(x.pct) + '" style="width:' + (x.pct || 0) + '%"></i></span><b class="num" style="color:var(--txt-strong,var(--txt))">' + (x.pct == null ? "—" : x.pct + " %") +
          '</b></div><div class="cote">' + (x.prevision ? pill(x.prevision, x.alerte ? "d" : "ok") : "") + "</div></div>").join("") + "</div>",
          '<button class="btn s" data-a="module" data-e="historique" data-v="" data-ou="Historique › Prévision du disque">Prévision</button>' + demande("Qu’est-ce qui prend la place ?", "Qu’est-ce qui prend la place sur le disque de la machine " + ((d.machine || {}).nom || "") + ", et que puis-je libérer sans risque ?"));
    },
    proc() {
      const d = D();
      if (!d.ressources && !(d.processus || []).length) return tete("Processus et mémoire", "ce qui tourne sur la machine", age()) + inconnu("Les processus");
      const q = S.q.toLowerCase(), l = (d.processus || []).filter((p) => !q || (p.commande + " " + p.utilisateur).toLowerCase().includes(q)), r = d.ressources || {}, oom = d.oom;
      let corps;
      if (S.groupe) {
        const g = {}; l.forEach((p) => { g[p.utilisateur] = g[p.utilisateur] || [0, 0]; g[p.utilisateur][0] += p.cpu; g[p.utilisateur][1]++; });
        corps = '<div class="rows">' + Object.keys(g).sort((a, b) => g[b][0] - g[a][0]).map((u) => '<div class="row"><div class="nm"><b class="mono">' + esc(u) + "</b><small>" + g[u][1] + ' processus</small></div><div class="mil"><span class="pbar"><i class="' + (g[u][0] > 50 ? "d" : g[u][0] > 20 ? "w" : "") +
          '" style="width:' + Math.min(g[u][0], 100) + '%"></i></span><b class="num" style="color:var(--txt-strong,var(--txt))">' + fr(g[u][0]) + ' %</b></div><div class="cote"></div></div>').join("") + "</div>";
      } else {
        corps = '<div class="cts">' + (l.map((p) => {
          const ouvert = S.pr === p.commande, nom = court(p.commande);
          return '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl large" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="pr" data-n="' + esc(p.commande) + '"><span class="nm"><b class="mono" title="' + esc(p.commande) + '">' + esc(p.commande) + "</b><small>utilisateur " + esc(p.utilisateur) +
            '</small></span><span class="c2"></span><span class="c3"></span><span class="c4"><b class="num" style="font-size:13.5px;color:var(--' + (p.cpu > 50 ? "danger" : p.cpu > 20 ? "warn" : "txt-strong") + ')">' + fr(p.cpu) + ' %</b><small>du processeur</small></span><span class="chev">›</span></button>' +
            (ouvert ? '<div class="ctf"><div class="bloc" style="grid-column:1/-1"><h3>La commande</h3><p class="dit mono" style="font-size:12.5px;word-break:break-all">' + esc(p.commande) + '</p></div><div class="gestes" style="grid-column:1/-1;align-items:center"><span style="flex:1"></span>' +
              cass([["Que fait-il ?", "Que fait le processus « " + nom + " » sur la machine ?"], ["Est-ce normal ?", "Est-ce normal que « " + nom + " » prenne " + fr(p.cpu) + " % du processeur sur la machine ?"], ["Que faire ?", "Le processus « " + nom + " » pèse sur la machine : que me conseilles-tu, sans rien casser ?"]]) + "</div></div>" : "") + "</div>";
        }).join("") || '<p class="vide">Aucun processus ne correspond.</p>') + "</div>";
      }
      let h = tete("Processus et mémoire", "ce qui tourne sur la machine, le plus gourmand d’abord", age());
      h += sec("Les processus", l.length + " sur " + (d.processus || []).length + " relevés · relus toutes les 5 s · un clic ouvre la fiche", corps,
        '<input type="search" placeholder="Filtrer…" aria-label="Filtrer les processus" value="' + esc(S.q) + '" data-s="q" id="mc-q"><button class="btn s" aria-pressed="' + S.groupe + '" data-a="groupe">' + (S.groupe ? "Un par un" : "Par utilisateur") + "</button>");
      if (r.ram_go && r.ram_go[1]) {
        const tot = r.ram_go[1], pris = r.ram_go[0] || 0;
        h += sec("La mémoire", fr(tot) + " Go", '<div class="pile"><i style="width:' + (pris / tot * 100).toFixed(1) + '%;background:var(--accent)" title="utilisée"></i><i style="width:' + ((tot - pris) / tot * 100).toFixed(1) + '%;background:var(--line-strong,var(--line))" title="disponible"></i></div>' +
          '<div class="leg"><span><i style="background:var(--accent);height:10px"></i>utilisée ' + fr(pris) + ' Go</span><span><i style="background:var(--line-strong,var(--line));height:10px"></i>disponible ' + fr(tot - pris) + " Go, cache compris</span>" +
          (r.swap_go && r.swap_go[1] ? "<span>échange " + fr(r.swap_go[0]) + " sur " + fr(r.swap_go[1]) + " Go</span>" : "") + "</div>",
          cass([["Qui prend la mémoire ?", "Qui consomme la mémoire sur la machine en ce moment, et est-ce normal ?"], ["Risque-t-on un plantage ?", "Y a-t-il un risque que des processus soient tués faute de mémoire sur la machine ? Que faire pour l’éviter ?"]]));
      }
      h += sec("Tués faute de mémoire", "OOM · les dernières 24 h", oom == null ? '<p class="vide">Inconnu : le collecteur n’a pas répondu.</p>' : oom.length ? '<div class="rows">' + oom.map((o, i) => '<div class="row"><div class="nm"><b class="mono">' + esc(o.processus) + "</b><small>" + esc(String(o.quand).replace("T", " ").slice(0, 16)) +
        '</small></div><div class="mil">occupait <b class="num" style="color:var(--danger)">' + fr(o.mo / 1024) + ' Go</b></div><div class="cote">' + pill("tué par le noyau", "d") + demande("Pourquoi ?", "Pourquoi " + o.processus + " a-t-il été tué faute de mémoire sur la machine, et comment éviter que cela recommence ?") +
        '<button class="btn s" data-a="acquitter" data-i="' + i + '">Acquitter</button></div></div>').join("") + "</div>" : '<p class="vide">Aucun processus tué faute de mémoire.</p>',
        (oom && oom.length ? '<button class="btn s" data-a="acquitter" data-i="tous">Tout acquitter</button>' : "") + demande("Demander", "Y a-t-il eu des processus tués faute de mémoire récemment sur la machine, et pourquoi ?"));
      return h;
    },
    services() {
      const d = D(), sv = d.services;
      if (sv == null) return tete("Services", "les unités systemd de la machine", age()) + inconnu("Les services");
      const FAM = ["tous", "en échec", "maison", "web", "courrier", "données", "réseau", "sécurité", "système"], q = S.svQ.toLowerCase();
      const l = sv.suivis.filter((s) => (S.svF === "tous" || (S.svF === "en échec" ? s.etat === "echec" : s.famille === S.svF)) && (!q || (s.unite + " " + s.description).toLowerCase().includes(q))), ko = sv.suivis.filter((s) => s.etat === "echec");
      const MOT = { actif: ["actif", "ok"], echec: ["en échec", "d"], repos: ["au repos", ""], arret: ["arrêté", "w"] };
      const GESTE = { noyau: "Relancer", collecteur: "Redémarrer", ollama: "Relancer", nginx: "Recharger" };
      const ligne = (s) => {
        const ouvert = S.sv === s.unite, mot = MOT[s.etat] || [s.etat, ""];
        return '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="sv" data-n="' + esc(s.unite) + '"><span class="nm"><b class="mono">' + esc(s.unite) + "</b><small>" + esc(s.description || s.systemd) +
          '</small></span><span class="c2"><span style="font-size:13.5px;color:var(--txt-strong,var(--txt))">' + esc(s.famille) + "</span><small>" + (s.au_demarrage ? "démarre avec la machine" : "ne démarre pas avec la machine") + '</small></span><span class="c3">' +
          (s.ports.length ? s.ports.map((p) => '<span class="pc">' + esc(p) + "</span>").join("") : "<small>aucun port</small>") + '</span><span class="c4">' + pill(mot[0], mot[1]) + "<small>" + esc(s.sous_etat) + '</small></span><span class="chev">›</span></button>' +
          (ouvert ? '<div class="ctf"><div class="bloc" style="grid-column:1/-1"><h3>Ce que c’est</h3><p class="dit">' + esc(s.description || s.systemd || "—") + "</p>" + (s.systemd && s.description ? '<p class="dit" style="color:var(--txt-faint);font-size:12.5px">systemd : ' + esc(s.systemd) + "</p>" : "") + "</div>" +
            '<div class="bloc"><h3>État</h3><dl class="paires un"><div><dt>État</dt><dd>' + pill(mot[0], mot[1]) + " " + esc(s.sous_etat) + "</dd></div><div><dt>Au démarrage</dt><dd>" + (s.au_demarrage ? "se lance avec la machine" : "ne se lance pas avec la machine") + "</dd></div></dl></div>" +
            '<div class="bloc"><h3>Écoute sur</h3><p class="dit">' + (s.ports.length ? s.ports.map((p) => '<span class="pc">' + esc(p) + "</span>").join(" ") + ' <small><a data-a="module" data-e="securite" data-v="exposition" data-ou="Sécurité › Exposition">qui peut les joindre →</a></small>' : "aucun port") + "</p>" +
            (s.protege ? '<p class="dit" style="color:var(--warn)">' + esc(s.protege) + "</p>" : "") + "</div>" +
            '<div class="gestes" style="grid-column:1/-1;align-items:center">' + (s.geste ? '<button class="btn s ' + (s.geste === "noyau" ? "d" : "") + '" data-a="svc" data-g="' + s.geste + '">' + GESTE[s.geste] + '</button><button class="btn s" data-a="journal" data-g="' + s.geste + '" data-n="' + esc(s.unite) + '">Journal</button>' : "") +
            (s.etat === "echec" ? demande("Demander à Cassandra de le réparer", "Le service " + s.unite + " est en échec sur la machine : lis son journal, dis-moi pourquoi, et propose-moi un plan pour le réparer.", "p") : "") + '<span style="flex:1"></span>' +
            cass([["À quoi sert-il ?", "À quoi sert le service " + s.unite + " sur la machine, et que se passe-t-il si je l’arrête ?"], ["Va-t-il bien ?", "Le service " + s.unite + " va-t-il bien sur la machine ? Dis-moi ce qui cloche."], ["Le régler", "Comment le service " + s.unite + " est-il réglé sur la machine, et que me conseilles-tu d’ajuster ?"]]) + "</div></div>" : "") + "</div>";
      };
      let h = tete("Services", sv.actifs + " actifs · " + sv.inactifs + " inactifs · " + sv.echecs.length + " en échec", age());
      if (ko.length) {
        h += '<section class="carte sec bandeau-v"><div class="verdict"><div class="vm d"></div><div style="flex:1"><p class="vt">' + ko.length + " service" + (ko.length > 1 ? "s" : "") + " en échec : " + ko.map((s) => esc(s.unite)).join(", ") + '</p><div class="gestes">' +
          demande("Demander à Cassandra de réparer", "Ces services sont en échec sur la machine : " + ko.map((s) => s.unite).join(", ") + ". Lis leurs journaux, dis-moi pourquoi, et propose-moi un plan pour les réparer.", "p") +
          '<button class="btn s" data-a="svF" data-f="en échec">Ne voir qu’eux</button><button class="btn s" data-a="reinitialiser" title="systemctl reset-failed : elles ne sont plus comptées en panne ; rien n’est redémarré">Réinitialiser le compteur</button></div></div></div></section>';
      }
      h += sec("Les services", l.length + " sur " + sv.suivis.length + " suivis de près · un clic ouvre la fiche", '<div class="chips">' + FAM.map((f) => '<button class="chip" aria-pressed="' + (S.svF === f) + '" data-a="svF" data-f="' + f + '">' + f + (f === "en échec" && ko.length ? " · " + ko.length : "") + "</button>").join("") + '</div><div class="cts">' +
        (l.map(ligne).join("") || '<p class="vide">Aucun service ne correspond.</p>') + '</div><p class="note">Les ' + Math.max(0, sv.total - sv.suivis.length) + " autres unités de la machine restent dans le Sensorium, famille « Services ». Les tâches planifiées ont leur écran, Automatismes.</p>",
        '<input type="search" placeholder="Filtrer…" aria-label="Filtrer les services" value="' + esc(S.svQ) + '" data-s="svQ" id="mc-q"><button class="btn s" data-a="module" data-e="sensorium" data-v="carte" data-ou="Sensorium">Sensorium</button>');
      return h;
    },
    conteneurs() {
      const d = D(), ct = d.conteneurs;
      if (ct == null) return tete("Conteneurs", "Docker sur la machine", age()) + inconnu("Les conteneurs");
      const ko = ct.filter((c) => !c.tourne).length;
      const ligne = (c) => {
        const ouvert = S.ct === c.nom, coul = c.pause ? "w" : c.tourne ? "ok" : "d", charge = c.tourne && !c.pause && c.cpu != null ? fr(c.cpu, 2) + " % · " + c.memoire : "—";
        return '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="ct" data-n="' + esc(c.nom) + '"><span class="nm"><b class="mono">' + esc(c.nom) + '</b><small>conteneur Docker</small></span><span class="c2"><span class="mono">' + esc(c.image) +
          "</span><small>" + (c.image_age_j != null ? "image construite il y a " + c.image_age_j + " j" : "") + '</small></span><span class="c3"></span><span class="c4">' + pill(c.etat, coul) + '<small class="num">' + esc(charge) + '</small></span><span class="chev">›</span></button>' +
          (ouvert ? '<div class="ctf"><div class="bloc"><h3>Image</h3><dl class="paires un"><div><dt>Image</dt><dd class="mono">' + esc(c.image) + "</dd></div><div><dt>Construite</dt><dd>" + (c.image_age_j != null ? "il y a " + c.image_age_j + " jours" : "—") +
            '</dd></div><div><dt>Failles connues</dt><dd><a data-a="module" data-e="securite" data-v="outils" data-ou="Sécurité › Outils (Trivy)">Sécurité › Outils →</a></dd></div></dl></div><div class="bloc"><h3>Marche</h3><dl class="paires un"><div><dt>État</dt><dd>' + esc(c.etat) +
            "</dd></div><div><dt>Ressources</dt><dd>" + (c.tourne && c.cpu != null ? "processeur " + fr(c.cpu, 2) + " % · mémoire " + esc(c.memoire) : "—") + '</dd></div></dl></div><div class="gestes" style="grid-column:1/-1;align-items:center"><span style="flex:1"></span>' +
            cass([["Que fait-il ?", "Que fait le conteneur " + c.nom + " sur la machine ?"], ["Faire le point", "Fais-moi le point sur le conteneur " + c.nom + " de la machine : ce qu’il fait, ses ports, son image, ce qui cloche."]]) + "</div></div>" : "") + "</div>";
      };
      return tete("Conteneurs", (ct.length - ko) + " sur " + ct.length + " tournent", age()) + sec("Les conteneurs", "Docker · un clic ouvre la fiche", ct.length ? '<div class="cts">' + ct.map(ligne).join("") + "</div>" : '<p class="vide">Aucun conteneur sur cette machine.</p>',
        '<button class="btn s" data-a="module" data-e="securite" data-v="outils" data-ou="Sécurité › Outils (Trivy)" title="Les failles connues dans les images">Failles des images</button>');
    },
    sessions() {
      const d = D(), se = d.sessions, rf = d.refus;
      if (se == null) return tete("Sessions", "qui est connecté à la machine", age()) + inconnu("Les sessions");
      const ligne = (s, i) => {
        const k = s.utilisateur + "@" + s.adresse, ouvert = S.se === k, quoi = s.anonyme ? "Connexion SSH pas encore identifiée" : s.type === "ftp" ? "Dépôt de fichiers par FTP" : "Session SSH de " + s.utilisateur;
        const lecture = s.anonyme ? "L’utilisateur « sshd » veut dire que personne n’est encore entré : quelqu’un frappe à la porte. Le plus souvent, c’est une tentative automatique, qui sera refusée." :
          s.reseau === "Tailscale" ? "Une session ouverte depuis une machine de ton réseau privé." : s.reseau === "Internet" ? "Une session ouverte depuis Internet." : "Une session ouverte depuis " + s.reseau + ".";
        return '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="se" data-n="' + esc(k) + '"><span class="nm"><b class="mono">' + esc(s.utilisateur) + "</b><small>" + esc(quoi) + '</small></span><span class="c2"><span class="mono">' + esc(s.adresse) +
          "</span><small>" + esc(s.reseau) + (s.machine ? " · la machine " + esc(s.machine) : "") + '</small></span><span class="c3" style="flex-direction:column;align-items:flex-start"><span style="font-size:13.5px;color:var(--txt-strong,var(--txt))">depuis ' + esc(s.depuis) + "</span><small>" + esc(s.type.toUpperCase()) +
          '</small></span><span class="c4">' + pill(s.anonyme ? "pas identifiée" : s.reseau === "Tailscale" ? "réseau privé" : "à regarder", s.anonyme ? "w" : s.reseau === "Tailscale" ? "ok" : "") + '</span><span class="chev">›</span></button>' +
          (ouvert ? '<div class="ctf"><div class="bloc" style="grid-column:1/-1"><h3>Ce que c’est</h3><p class="dit">' + esc(lecture) + '</p></div><div class="bloc"><h3>D’où elle vient</h3><dl class="paires un"><div><dt>Adresse</dt><dd class="mono">' + esc(s.adresse) + "</dd></div><div><dt>Réseau</dt><dd>" + esc(s.reseau) +
            "</dd></div>" + (s.machine ? "<div><dt>Machine</dt><dd>" + esc(s.machine) + "</dd></div>" : "") + '</dl></div><div class="bloc"><h3>Depuis quand</h3><dl class="paires un"><div><dt>Ouverte</dt><dd>' + esc(s.depuis) + " (heure du serveur)</dd></div><div><dt>Type</dt><dd>" + esc(s.type.toUpperCase()) +
            '</dd></div></dl></div><div class="gestes" style="grid-column:1/-1;align-items:center"><button class="btn s d" data-a="deconnecter" data-i="' + i + '">Déconnecter</button><span style="flex:1"></span>' +
            cass([["Qui est-ce ?", "Qui se cache derrière la session " + s.utilisateur + " depuis " + s.adresse + " sur la machine ?"], ["Est-ce normal ?", "La session " + s.utilisateur + " depuis " + s.adresse + " sur la machine est-elle normale ? Que me conseilles-tu ?"]]) + "</div></div>" : "") + "</div>";
      };
      let h = tete("Sessions", "qui est connecté à la machine · " + se.length + " ouverte" + (se.length > 1 ? "s" : "") + (rf && rf.total != null ? " · " + rf.total + " tentatives refusées dans l’heure" : ""), age());
      h += sec("Sessions ouvertes", "un clic ouvre la fiche", se.length ? '<div class="cts">' + se.map(ligne).join("") + "</div>" : '<p class="vide">Aucune session ouverte.</p>', '<button class="btn s" data-a="module" data-e="securite" data-v="acces" data-ou="Sécurité › Accès">Sécurité › Accès</button>');
      if (rf) {
        const max = Math.max.apply(null, rf.adresses.map((a) => a[1]).concat([1]));
        h += sec("Tentatives refusées", esc(rf.texte.split(" · ")[0]), rf.adresses.length ? '<div class="rows">' + rf.adresses.map((a) => '<div class="row"><div class="nm"><b class="mono">' + esc(a[0]) + "</b><small>" + a[1] + ' tentatives en une heure</small></div><div class="mil"><span class="pbar"><i class="w" style="width:' +
          Math.round(a[1] / max * 100) + '%"></i></span></div><div class="cote"></div></div>').join("") + "</div>" : '<p class="vide">' + esc(rf.texte) + "</p>",
          '<button class="btn s" data-a="module" data-e="securite" data-v="defenses" data-ou="Sécurité › Défenses">Sécurité › Défenses</button>' + cass([["Est-on attaqué ?", "Y a-t-il une attaque en cours sur le SSH de la machine ? Que me conseilles-tu ?"]]));
      }
      return h;
    },
    fiche() {
      const d = D(), m = d.machine || {}, r = d.ressources || {}, lg = d.logiciels || { installes: [], absents: [] };
      if (muet() || !m.nom) return tete("La fiche de la machine", "ce qu’elle est", age()) + inconnu("La fiche de la machine");
      const p = (dt, dd) => "<div><dt>" + dt + "</dt><dd>" + dd + "</dd></div>";
      const bloc = (t, meta, corps, droite) => sec(t, meta, corps, droite).replace('class="carte sec"', 'class="carte sec" style="margin:0"');
      const texte = ["Machine : " + m.nom, "Système : " + [m.os, m.archi, m.nature].filter(Boolean).join(" · "), "Noyau : " + m.noyau, r.ram_go ? "Mémoire : " + fr(r.ram_go[1]) + " Go" : "", "Adresses : " + (m.interfaces || []).map((i) => (i.v4[0] || i.v6[0] || "?") + " (" + i.nom + ")").join(", "), "Allumée depuis : " + m.allumee].filter(Boolean).join("\n");
      let h = tete("La fiche de la machine", "ce qu’elle est, ce qu’elle porte", age());
      h += '<section class="carte sec bandeau-v"><div class="verdict"><div class="vm ' + (m.redemarrage ? "d" : "") + '"></div><div style="flex:1;min-width:0"><p class="vt mono" style="font-size:22px">' + esc(m.nom) + '</p><div class="puces" style="margin-top:8px">' +
        [m.os, m.nature && "nature : " + m.nature, r.ram_go && r.ram_go[1] && fr(r.ram_go[1]) + " Go de mémoire", r.disque_go && r.disque_go[1] && fr(r.disque_go[1], 0) + " Go de disque", m.allumee && "allumée depuis " + m.allumee].filter(Boolean).map((x) => '<span class="puce">' + esc(x) + "</span>").join("") +
        (m.redemarrage ? '<span class="puce" style="border-color:var(--danger);color:var(--danger)">redémarrage requis</span>' : "") + '</div></div><div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end"><button class="btn s" data-a="copier" data-t="' + esc(texte) + '">Copier la fiche</button>' +
        cass([["Présente-la-moi", "Présente-moi la machine " + m.nom + " : ce qu’elle est, ce qu’elle porte, ce qui mérite mon attention."], ["Est-elle assez grande ?", "La machine " + m.nom + " est-elle bien dimensionnée pour ce qu’elle porte (processeur, mémoire, disque) ?"]]) + "</div></div></section>";
      h += '<div class="duo">';
      h += bloc("Identité", "qui elle est", '<dl class="paires un">' + p("Nom", '<span class="mono">' + esc(m.nom) + "</span>") + p("Système", esc(m.os) + (m.archi ? " <small>" + esc(m.archi) + "</small>" : "")) + (m.nature ? p("Nature", esc(m.nature === "none" ? "machine physique" : "machine virtuelle (" + m.nature + ")")) : "") +
        p("Noyau", '<span class="mono">' + esc(m.noyau || "—") + "</span>") + p("Allumée depuis", esc(m.allumee || "—")) + p("Redémarrage", m.redemarrage ? '<span style="color:var(--danger)">requis</span> <small>' + esc(m.redemarrage_texte) + "</small>" : "pas de redémarrage requis") + "</dl>");
      h += bloc("Matériel", "ce qu’elle a", '<dl class="paires un">' + p("Mémoire", r.ram_go && r.ram_go[1] ? fr(r.ram_go[1]) + " Go <small>" + fr(r.ram_go[0]) + " Go utilisés</small>" : "—") + p("Échange", r.swap_go && r.swap_go[1] ? fr(r.swap_go[1]) + " Go <small>" + fr(r.swap_go[0]) + " Go utilisés</small>" : "aucun") +
        p("Disque", r.disque_go && r.disque_go[1] ? fr(r.disque_go[1], 0) + " Go <small>" + fr(r.disque_go[0], 0) + " Go utilisés</small>" : "—") + "</dl>", '<button class="btn s" data-a="page" data-p="ressources">Ressources</button>');
      h += bloc("Stockage", "où sont les fichiers", '<div class="rows">' + (d.disques || []).map((x) => '<div class="row" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)"><div class="nm"><b class="mono">' + esc(x.montage) + "</b><small>" + (x.type ? esc(x.type) + " · " : "") + fr(x.utilise_go) + " sur " + fr(x.total_go) + " Go" +
        (x.inodes_pct != null ? " · inodes " + x.inodes_pct + " %" : "") + '</small></div><div class="mil" style="flex-direction:column;align-items:flex-start;gap:3px"><span style="display:flex;align-items:center;gap:8px;width:100%"><span class="pbar"><i class="' + niv(x.pct) + '" style="width:' + (x.pct || 0) +
        '%"></i></span><b class="num" style="color:var(--txt-strong,var(--txt))">' + (x.pct == null ? "—" : x.pct + " %") + '</b></span><small style="color:var(--' + (x.alerte ? "danger" : "txt-faint") + ');font-size:12.5px">' + esc(x.prevision.split(" (")[0]) + "</small></div></div>").join("") + "</div>",
        '<button class="btn s" data-a="module" data-e="historique" data-v="" data-ou="Historique › Prévision du disque">Prévision</button>');
      h += bloc("Réseau", "comment on la joint", '<div class="rows">' + (m.interfaces || []).map((i) => '<div class="row" style="grid-template-columns:minmax(0,.7fr) minmax(0,1.6fr) auto"><div class="nm"><b class="mono">' + esc(i.nom) + "</b><small>" + esc(i.etat) +
        '</small></div><div class="mil" style="flex-direction:column;align-items:flex-start;gap:1px"><span class="mono" style="color:var(--txt-strong,var(--txt))">' + esc(i.v4.join(", ") || "—") + '</span><small class="mono" style="color:var(--txt-faint);font-size:12px">' + esc(i.v6.join(", ")) + '</small></div><div class="cote">' +
        (i.defaut ? pill("route par défaut", "i") : "") + "</div></div>").join("") + '</div><dl class="paires un" style="margin-top:8px">' + p("Résolution DNS", esc(m.dns || "—")) + "</dl>", '<button class="btn s" data-a="module" data-e="securite" data-v="exposition" data-ou="Sécurité › Exposition">Exposition</button>');
      h += bloc("Horloge", "l’heure qu’elle croit", '<dl class="paires un">' + p("Synchronisation", esc(m.horloge || "—")) + p("Fuseau", '<span class="mono">' + esc(m.fuseau || "—") + "</span> <small>les heures de Cassandra sont celles du serveur</small>") + "</dl>");
      h += bloc("Protections de base", "résumé ici · réglé dans Sécurité", '<dl class="paires un">' + (m.pare_feu || []).map((x, i) => p("Pare-feu" + (i ? " (IPv6)" : ""), esc(x))).join("") + p("Mises à jour", esc((m.maj || {}).texte || "—")) + (m.taches ? p("Tâches planifiées", esc(m.taches)) : "") + "</dl>",
        '<button class="btn s" data-a="module" data-e="securite" data-v="maj" data-ou="Sécurité › Mises à jour et noyau">Mises à jour</button><button class="btn s" data-a="module" data-e="securite" data-v="parefeu" data-ou="Sécurité › Pare-feu">Pare-feu</button>');
      h += "</div>";
      h += sec("Logiciels installés", lg.installes.length + " trouvés · " + lg.absents.length + " cherchés et absents", '<div class="puces">' + lg.installes.map((x) => '<span class="puce mono">' + esc(x) + "</span>").join("") + "</div>" +
        (lg.absents.length ? '<p class="note" style="margin-top:10px">Cherchés et absents : ' + lg.absents.map((x) => '<span class="mono">' + esc(x) + "</span>").join(", ") + ".</p>" : ""), cass([["Que mettre à jour ?", "Quels logiciels de la machine " + m.nom + " sont en retard d’une version importante ou en fin de vie, et par quoi commencer ?"]]));
      if ((d.cassandra || []).length) h += sec("Cassandra sur cette machine", "ce qu’elle y a posé", '<dl class="paires un">' + d.cassandra.map((x) => { const t = x.titre.replace(/^[^—]+— /, ""); return p(esc(t.charAt(0).toUpperCase() + t.slice(1)), esc(x.texte)); }).join("") + "</dl>",
        '<button class="btn s" data-a="page" data-p="services">Ses services</button>');
      return h;
    },
  };
  function jauge(nom, valeur, pct, sous) { return '<div class="jg"><span>' + nom + '</span><b class="' + niv(pct) + '">' + valeur + '</b><div class="barre"><i class="' + niv(pct) + '" style="width:' + Math.min(pct || 0, 100) + '%"></i></div><em>' + sous + "</em></div>"; }
  function jauges() {
    const r = D().ressources; if (!r) return "";
    return jauge("Processeur", fr(r.cpu, 0) + " %", r.cpu, "charge " + r.charge.map((c) => fr(c, 2)).join(" · ") + " <small>(1, 5, 15 min)</small>") + jauge("Mémoire", fr(r.ram, 0) + " %", r.ram, fr(r.ram_go[0]) + " sur " + fr(r.ram_go[1]) + " Go") +
      jauge("Échange (swap)", fr(r.swap, 0) + " %", r.swap, fr(r.swap_go[0]) + " sur " + fr(r.swap_go[1]) + " Go") + jauge("Disque /", fr(r.disque, 0) + " %", r.disque, fr(r.disque_go[0], 0) + " sur " + fr(r.disque_go[1], 0) + " Go · " + fr(r.disque_libre_go, 0) + " Go libres");
  }
  function courbe() {
    const z = R && R.querySelector("#mc-courbe"); if (!z) return;
    const tr = (l, c) => { if (l.length < 2) return ""; const pts = l.map((v, i) => [(600 - (l.length - 1 - i) * (600 / 59)).toFixed(1), (140 - v * 1.3).toFixed(1)]); return '<path d="M' + pts.map((p) => p.join(",")).join(" L") + '" fill="none" stroke="' + c + '" stroke-width="2" vector-effect="non-scaling-stroke"/>'; };
    z.innerHTML = [0, 25, 50, 75, 100].map((v) => '<line x1="0" x2="600" y1="' + (140 - v * 1.3) + '" y2="' + (140 - v * 1.3) + '" stroke="var(--line)" vector-effect="non-scaling-stroke"/>').join("") + tr(S.hist.ram, "var(--violet,#7c5cfc)") + tr(S.hist.cpu, "var(--accent)");
  }

  // ───────────────────────── lire, relire, dessiner
  const visible = () => { const t = document.getElementById("tab-overview"); return !!(t && t.classList.contains("active") && t.dataset.vue === "machine" && document.visibilityState === "visible"); };
  function noterMesure() { const r = D().ressources; if (!r || r.cpu == null) return; S.hist.cpu.push(r.cpu); S.hist.ram.push(r.ram || 0); if (S.hist.cpu.length > 60) { S.hist.cpu.shift(); S.hist.ram.shift(); } }
  async function charger() {
    if (S.charge) return; S.charge = true;
    try { const d = await agir("vue.machine"); if (d && d.ok === false) { S.d = null; S.erreur = d.raison || "lecture refusée"; } else { S.d = d; S.erreur = ""; S.lu = Date.now(); noterMesure(); } }
    catch (e) { S.erreur = (e && e.message) || "la lecture a échoué"; if (!S.d) S.d = null; }
    S.charge = false; rendre();
  }
  // Toutes les cinq secondes : les mesures seules (une lecture légère), posées dans les tuiles sans redessiner la page.
  async function battre() {
    if (!visible() || !S.d || muet()) return;
    let m; try { m = await agir("sensorium.metriques"); } catch (e) { return; }
    if (!m || m.muet || !S.d.ressources) return;
    const r = S.d.ressources, n = (k) => (typeof m[k] === "number" ? m[k] : null);
    Object.assign(r, { cpu: n("cpu"), ram: n("ram"), swap: n("swap"), disque: n("disk"), charge: [n("load_1m"), n("load_5m"), n("load_15m")], ram_go: [n("ram_used_gb"), n("ram_total_gb")], swap_go: [n("swap_used_gb"), n("swap_total_gb")], disque_go: [n("disk_used_gb"), n("disk_total_gb")], disque_libre_go: n("disk_free_gb") });
    if (Array.isArray(m.top_processes)) S.d.processus = m.top_processes.map((p) => ({ utilisateur: String(p.user || ""), cpu: typeof p.cpu === "number" ? p.cpu : 0, commande: String(p.command || p.name || "?") }));
    noterMesure();
    if (!R) return;
    const a = R.querySelector("#mc-res"), b = R.querySelector("#mc-proc"), j = R.querySelector("#mc-jauges");
    if (a) a.innerHTML = corpsRes(); if (b) b.innerHTML = corpsProc(); if (j) { j.innerHTML = jauges(); courbe(); }
    if (S.page === "proc" && !S.pr && document.activeElement !== R.querySelector("#mc-q") && !document.querySelector(".kit-m")) rendre();
  }
  function rendre() {
    if (!R) return;
    const q = document.activeElement && document.activeElement.id === "mc-q" ? document.activeElement.dataset.s : "";
    R.innerHTML = (PAGES[S.page] || PAGES.vue)();
    courbe();
    if (q) { const i = R.querySelector("#mc-q"); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }
  }
  function page(p) { S.page = PAGES[p] ? p : "vue"; rendre(); const t = document.getElementById("tab-overview"); if (t) t.scrollTop = 0; if (R) R.scrollTop = 0; }

  // ───────────────────────── les gestes (ceux qui existent déjà)
  function feuille(titre, html) {
    const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
    const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.style.width = "min(760px,calc(100% - 32px))";
    m.innerHTML = "<h2>" + esc(titre) + "</h2>" + html + '<div class="acts"><button class="btn pri" data-c="fermer">Fermer</button></div>';
    const clore = () => { v.remove(); m.remove(); };
    v.addEventListener("click", clore); m.addEventListener("click", (e) => { if (e.target.closest("[data-c]")) clore(); }); m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(); });
    document.body.appendChild(v); document.body.appendChild(m); m.querySelector("[data-c]").focus();
  }
  const SVC = {
    noyau: ["Relancer le noyau de Cassandra ?", "<p>Tu seras déconnecté quelques secondes. Le geste part dans trois secondes.</p>", "Relancer", true, () => agir("securite.systeme_geste", { service: "noyau", action: "restart" }), "Le noyau se relance."],
    ollama: ["Relancer Ollama ?", "<p>Les modèles locaux sont déchargés puis rechargés à la demande.</p>", "Relancer", false, () => agir("securite.systeme_geste", { service: "ollama", action: "restart" }), "Ollama est relancé."],
    nginx: ["Recharger nginx ?", "<p>Sa configuration est testée d’abord ; si elle est fausse, rien ne change. Aucune coupure.</p>", "Recharger", false, () => agir("securite.systeme_geste", { service: "nginx", action: "reload" }), "nginx a relu sa configuration."],
    collecteur: ["Redémarrer le collecteur du Sensorium ?", "<p>Quelques secondes sans relevé, après sa passe en cours. Aucune mesure perdue.</p>", "Redémarrer", false, () => agir("sensorium.redemarrer", { quand: "apres_passe", motif: "demandé depuis La machine" }), "Le collecteur est redémarré."],
  };
  const A = {
    page: (b) => page(b.dataset.p),
    relever: () => { dire("Relève en cours…"); return charger(); },
    plier: (b) => b.closest(".sec").classList.toggle("plie"),
    plein: (b) => { const s = b.closest(".sec"); R.querySelectorAll(".sec.plein").forEach((x) => x !== s && x.classList.remove("plein")); s.classList.toggle("plein"); },
    ouvrir: (b) => { const k = b.dataset.k; S[k] = S[k] === b.dataset.n ? "" : b.dataset.n; rendre(); },
    groupe: () => { S.groupe = !S.groupe; rendre(); },
    svF: (b) => { S.svF = b.dataset.f; rendre(); },
    demander: async (b) => { if (typeof window.d19Demander === "function" && await window.d19Demander(b.dataset.q)) dire("La demande est écrite dans la conversation : relis-la, puis envoie.", "ok"); else dire("La conversation n’est pas ouverte : ouvre-la, puis redemande.", "err"); },
    module: (b) => { if (typeof window.d19Aller === "function" && window.d19Aller(b.dataset.e, b.dataset.v || "")) return; dire("« " + (b.dataset.ou || b.dataset.e) + " » n’est pas au menu de ce compte.", "err"); },
    copier: async (b) => { try { await navigator.clipboard.writeText(b.dataset.t); dire("La fiche est copiée.", "ok"); } catch (e) { feuille("La fiche, en texte", '<pre style="white-space:pre-wrap;margin:0">' + esc(b.dataset.t) + "</pre>"); } },
    decouverte: () => feuille("Découverte automatique", '<p class="note">Aucune vignette n’est écrite en dur : la page n’affiche que ce qui est trouvé sur la machine. Un module de Cassandra qui répond donne une vignette ; un logiciel trouvé sans module donne une vignette « détecté » ; le reste n’apparaît pas.</p><ul class="lst">' +
      ((D().voisins || []).map((v) => "<li><b>" + esc(v.titre) + "</b> — " + esc(v.etat === "module" ? "module présent" : v.etat === "muet" ? "module muet" : "détecté, sans module") + " · " + esc(v.preuve) + "</li>").join("") || "<li>Rien trouvé.</li>") + "</ul>"),
    acquitter: async (b) => { const l = D().oom || [], s = b.dataset.i === "tous" ? l.map((o) => o.signature) : [l[+b.dataset.i] && l[+b.dataset.i].signature].filter(Boolean); if (!s.length) return; await agir("securite.oom_acquitter", { signatures: s }); dire(s.length + " événement" + (s.length > 1 ? "s acquittés." : " acquitté."), "ok"); return charger(); },
    reinitialiser: async () => { if (!await K.confirmer("Réinitialiser les unités en échec ?", "<p>Elles ne seront plus comptées en panne. Rien n’est redémarré.</p>", "Réinitialiser")) return; await agir("securite.unites_reinitialiser", {}); dire("Le compteur des unités en échec est remis à zéro.", "ok"); return charger(); },
    deconnecter: async (b) => { const s = (D().sessions || [])[+b.dataset.i]; if (!s) return; if (!await K.confirmer("Déconnecter la session de " + s.utilisateur + " (" + s.adresse + ") ?", "<p>Son terminal est retrouvé par le courtier, puis fermé.</p>", "Déconnecter", true)) return;
      await agir("securite.session_fermer", { user: s.utilisateur, ip: s.adresse }); dire("La session est fermée.", "ok"); return charger(); },
    svc: async (b) => { const g = SVC[b.dataset.g]; if (!g) return; if (!await K.confirmer(g[0], g[1], g[2], g[3])) return; await g[4](); dire(g[5], "ok"); setTimeout(charger, 4000); },
    journal: async (b) => { const nom = { noyau: "noyau", collecteur: "sensorium", ollama: "ollama", nginx: "nginx" }[b.dataset.g]; const r = await agir("securite.journal_service", { service: nom });
      feuille("Journal de " + (b.dataset.n || nom), '<p class="note">Les 200 dernières lignes, en lecture seule.</p><pre style="margin:0;max-height:52vh;overflow:auto;font:11.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word">' + esc((r && r.texte) || "Le journal est vide.") + "</pre>"); },
  };
  const msg = (x) => (x && x.message) || String(x || "le geste a échoué");

  // ───────────────────────── le branchement : la page vit dans l'onglet de la vue d'ensemble, sous sa rubrique « machine »
  function monter() {
    const t = document.getElementById("tab-overview"); if (!t) return false;
    if (!document.getElementById("mc-css")) { const st = document.createElement("style"); st.id = "mc-css"; st.textContent = CSS; document.head.appendChild(st); }
    K.injecter();
    R = document.getElementById("mc19");
    if (!R) {
      R = document.createElement("div"); R.id = "mc19"; R.className = "mc"; t.appendChild(R);
      R.addEventListener("click", (e) => { const b = e.target.closest("[data-a]"); if (!b || b.disabled || !R.contains(b)) return; const f = A[b.dataset.a]; if (!f) return; e.preventDefault(); e.stopPropagation(); Promise.resolve().then(() => f(b)).catch((x) => dire(msg(x), "err")); });
      R.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches(".tu")) e.target.click(); if (e.key === "Escape") R.querySelectorAll(".sec.plein").forEach((x) => x.classList.remove("plein")); });
      R.addEventListener("input", (e) => { const i = e.target.closest("[data-s]"); if (i) { S[i.dataset.s] = i.value; rendre(); } });
    }
    return true;
  }
  function ouvrir(p) {
    if (!monter()) return;
    S.page = PAGES[p] ? p : "vue";
    rendre(); charger();
    if (!S.minuteurs.length) { S.minuteurs.push(setInterval(battre, 5000)); S.minuteurs.push(setInterval(() => { if (visible()) charger(); }, 60000)); }
  }
  // La vue d'ensemble pose la rubrique (data-vue) ; quand c'est « machine », la page prend la place.
  function crocheter() {
    const origine = window.vuAller;
    if (typeof origine !== "function" || origine.__mc) return false;
    const neuf = function (sec) { const r = origine.apply(this, arguments); if (sec === "machine") ouvrir("vue"); return r; };
    neuf.__mc = true; window.vuAller = neuf;
    // L'ancien tiroir « Détails système » n'a plus d'entrée : tout ce qui l'ouvrait encore mène à la page.
    window.ouvrirSysteme = function () { if (typeof window.d19Aller === "function" && window.d19Aller("panorama", "machine")) return; if (typeof window.switchTab === "function") window.switchTab("overview"); window.vuAller("machine"); };
    return true;
  }
  if (!crocheter()) document.addEventListener("DOMContentLoaded", crocheter);
  window.mcPage = function (p) { ouvrir(p || "vue"); };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
