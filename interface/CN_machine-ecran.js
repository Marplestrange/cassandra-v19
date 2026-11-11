// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La machine : la page du Panorama qui remplace le tiroir « Détails système » (maquette : do
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f66958
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La machine : la page du Panorama qui remplace le tiroir « Détails système » (maquette : docs/CN_maquette-systeme.html).
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f66958 ▼▼▼
// La machine : la page du Panorama qui remplace le tiroir « Détails système » (maquette : docs/CN_maquette-systeme.html).
// Une seule page où tout se voit d'un coup d'œil, une tuile par sujet ; le détail d'un sujet s'ouvre au clic, « ‹ La machine » y ramène.
// Tout vient d'UNE lecture, vue.machine, qui compose ce que les modules relèvent déjà ; les ressources et les processus se relisent seuls
// toutes les cinq secondes (sensorium.metriques), le reste chaque minute. Rien n'est inventé : une source muette dit « inconnu ».
// Lot 1 : ce qui se lit déjà, et les gestes qui existent (acquitter, réinitialiser, déconnecter, relancer et lire les quatre services de la maison).
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir, dire = K.dire;
  const CSS = "#tab-overview[data-vue=\"machine\"]>:not(#mc19){display:none!important}#tab-overview[data-vue=\"machine\"]>#mc19{flex:1 1 auto;min-height:0;min-width:0;overflow-y:auto;overflow-x:hidden;padding:2px 8px 28px 2px}#tab-overview:not([data-vue=\"machine\"])>#mc19{display:none}.mc{color:var(--txt);font:15px/1.5 Inter,system-ui,-apple-system,\"Segoe UI\",sans-serif;padding:6px 4px 48px;max-width:1140px;margin:0 auto}.mc *{box-sizing:border-box}.mc a{cursor:pointer;color:var(--accent)}.mc h2,.mc h3{margin:0}.mc .tu:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.mc .mono,.mc code,.mc .num{font-family:\"JetBrains Mono\",ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}.mc code{font-size:.92em;color:var(--txt-strong,var(--txt))}.mc button{font:inherit;color:inherit;cursor:pointer}.mc :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:8px}.mc svg.i{width:17px;height:17px;flex:none;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.mc .carte{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);backdrop-filter:blur(18px)}.mc .fil{font-size:13px;color:var(--txt-faint);margin:2px 0 6px}.mc h1{font-size:26px;margin:0 0 4px;color:var(--txt-strong,var(--txt));letter-spacing:-.2px}.mc .tete{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px}.mc .tete .meta{font-size:13px;color:var(--txt-faint);margin-right:auto;flex:1 1 320px}.mc .btn{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:7px 13px;font-size:14px;color:var(--txt-strong,var(--txt));display:inline-flex;align-items:center;gap:7px}.mc .btn:hover{border-color:var(--accent)}.mc .btn.p{background:var(--accent);border-color:var(--accent);color:#fff}:root[data-theme=\"dark\"] .mc .btn.p{color:#06231f}.mc .btn.d{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 12%,transparent)}.mc .btn:disabled{opacity:.5;cursor:not-allowed}.mc .btn.s{padding:4px 10px;font-size:13px}.mc .sec{padding:16px 18px;margin-bottom:16px}.mc .sec h2{font-size:16px;margin:0;color:var(--txt-strong,var(--txt))}.mc .sh{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px}.mc .sh .meta{font-size:12.5px;color:var(--txt-faint)}.mc .sh .dr{margin-left:auto;display:flex;gap:6px;align-items:center}.mc .cmd{background:transparent;border:0;color:var(--txt-faint);border-radius:8px;padding:2px 7px;font-size:14px}.mc .cmd:hover{background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--txt-strong,var(--txt))}.mc .sec.plie>:not(.sh){display:none}.mc .sec.plie .sh{margin-bottom:0}.mc .sec.plein{position:fixed;inset:14px;z-index:9000;overflow:auto;margin:0;background:var(--surface-solid,var(--surface))}.mc .age{font-size:12px;color:var(--txt-faint);display:inline-flex;align-items:center;gap:6px}.mc .age::before{content:\"\";width:7px;height:7px;border-radius:50%;background:var(--ok)}.mc .age.mu::before{background:var(--danger)}.mc .age.mu{color:var(--danger)}.mc .verdict{display:flex;gap:14px;align-items:stretch}.mc .vm{width:5px;border-radius:4px;background:var(--ok);flex:none}.mc .vm.w{background:var(--warn)}.mc .vm.d{background:var(--danger)}.mc .vm.n{background:var(--line-strong,var(--line))}.mc .verdict p{margin:0}.mc .vt{font-size:19px;font-weight:700;color:var(--txt-strong,var(--txt))}.mc .vs{color:var(--txt-soft);font-size:14px;margin-top:2px!important}.mc .gestes{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.mc .jauges{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}.mc .jg{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:11px 13px}.mc .jg span{display:block;font-size:12.5px;color:var(--txt-faint)}.mc .jg b{display:block;font:650 24px/1.2 \"JetBrains Mono\",ui-monospace,monospace;color:var(--txt-strong,var(--txt))}.mc .jg b.w{color:var(--warn)}.mc .jg b.d{color:var(--danger)}.mc .jg b.mu{color:var(--txt-faint)}.mc .jg em{display:block;font-style:normal;font-size:12.5px;color:var(--txt-soft)}.mc .barre{height:5px;border-radius:3px;background:var(--line);margin:7px 0 4px;overflow:hidden}.mc .barre i{display:block;height:100%;border-radius:3px;background:var(--accent);transition:width .6s}.mc .barre i.w{background:var(--warn)}.mc .barre i.d{background:var(--danger)}.mc .courbe{width:100%;height:150px;display:block}.mc .leg{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--txt-faint);margin-top:8px}.mc .leg i{display:inline-block;width:10px;height:3px;border-radius:2px;margin-right:5px;vertical-align:3px}.mc .pl{display:inline-flex;align-items:center;gap:5px;font-size:12px;border-radius:999px;padding:2px 9px;background:var(--line);color:var(--txt-soft);white-space:nowrap}.mc .pl::before{content:\"\";width:6px;height:6px;border-radius:50%;background:currentColor}.mc .pl.ok{background:color-mix(in srgb,var(--ok) 12%,transparent);color:var(--ok)}.mc .pl.w{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.mc .pl.d{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger)}.mc .pl.i{background:color-mix(in srgb,var(--info,var(--accent)) 12%,transparent);color:var(--info,var(--accent))}.mc .rows{display:grid;gap:6px}.mc .row{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1.2fr) auto;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:9px 13px}.mc .row .nm{min-width:0}.mc .row .nm b{display:block;color:var(--txt-strong,var(--txt));overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:650}.mc .row .nm small{color:var(--txt-faint);font-size:12.5px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc .row .mil{font-size:13px;color:var(--txt-soft);min-width:0;display:flex;align-items:center;gap:8px}.mc .row .cote{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}@media (max-width:760px){.mc .row{grid-template-columns:1fr}.mc .row .cote{justify-content:flex-start}}.mc .paires{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:2px 26px;margin:0}.mc .paires div{display:flex;gap:10px;padding:7px 0;border-bottom:1px dashed var(--line);font-size:14px;align-items:baseline}.mc .paires dt{color:var(--txt-faint);flex:0 0 118px;font-size:13px}.mc .paires dd{margin:0;color:var(--txt-strong,var(--txt));min-width:0}.mc .paires dd small{display:block;color:var(--txt-soft);font-size:12.5px}.mc .vide{color:var(--txt-faint);font-size:14px;padding:6px 0}.mc .muet{background:color-mix(in srgb,var(--danger) 12%,transparent);border:1px solid var(--line);border-radius:13px;padding:11px 14px;font-size:14px;color:var(--txt-strong,var(--txt))}.mc .note{font-size:12.5px;color:var(--txt-faint);margin-top:10px}.mc input[type=search]{font:inherit;color:var(--txt-strong,var(--txt));background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:11px;padding:6px 11px;min-width:0;width:220px}.mc .pbar{flex:1;height:5px;border-radius:3px;background:var(--line);overflow:hidden;min-width:60px}.mc .pbar i{display:block;height:100%;background:var(--accent)}.mc .pbar i.w{background:var(--warn)}.mc .pbar i.d{background:var(--danger)}.mc .puces{display:flex;gap:6px;flex-wrap:wrap}.mc .puce{background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:3px 9px;font-size:12.5px;color:var(--txt-strong,var(--txt))}.mc .puce:hover{border-color:var(--accent)}.mc .bandeau-v{padding:14px 18px;margin-bottom:6px}.mc .bandeau-v .vt{font-size:18px}.mc .note-sante{text-align:right;min-width:150px;cursor:help}.mc .note-sante span,.mc .note-sante em{display:block;font-size:12.5px;color:var(--txt-faint);font-style:normal}.mc .note-sante b{display:block;font-size:28px;line-height:1.1}.mc .note-sante b small{font-size:13px;color:var(--txt-faint)}.mc .gt{font-size:11px;letter-spacing:.9px;text-transform:uppercase;color:var(--txt-faint);margin:14px 4px 8px;font-weight:650;display:flex;align-items:center;gap:8px;min-height:26px}.mc .gt .btn{margin-left:auto;text-transform:none;letter-spacing:0}.mc .gt span{text-transform:none;letter-spacing:0;font-weight:500}.mc .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:10px}.mc .tu{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 13px 10px;display:flex;flex-direction:column;gap:5px;cursor:pointer;box-shadow:var(--shadow-glass);min-height:158px;min-width:0}.mc .tu:hover{border-color:var(--accent);background:var(--surface-solid,var(--surface))}.mc .tu.ext{background:var(--surface);box-shadow:none}.mc .tu.mu>:not(.tt):not(.tp){opacity:.42;filter:grayscale(1)}.mc .tu .tt{display:flex;align-items:center;gap:8px;color:var(--txt-strong,var(--txt));font-size:14px;margin-bottom:2px}.mc .tu .tt b{font-weight:650}.mc .tu .tt .pl{margin-left:auto}.mc .tu .gr{font:650 25px/1.1 \"JetBrains Mono\",ui-monospace,monospace;color:var(--txt-strong,var(--txt))}.mc .tu .gr.w{color:var(--warn)}.mc .tu .gr.d{color:var(--danger)}.mc .tu .gr.mu{color:var(--txt-faint)}.mc .tu .cc{display:flex;flex-direction:column;gap:5px}.mc .tu .li{font-size:12.5px;color:var(--txt-soft);display:flex;gap:8px;align-items:center;min-width:0}.mc .tu .li .n{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc .tu .li small{color:var(--txt-faint)}.mc .tu .li b{color:var(--txt-strong,var(--txt));font-weight:600;font-size:12px;white-space:nowrap}.mc .tu .mb{display:grid;grid-template-columns:74px 1fr 42px;gap:8px;align-items:center;font-size:12.5px;color:var(--txt-soft)}.mc .tu .mb b{text-align:right;font-size:12px}.mc .tu .tp{margin-top:auto;padding-top:5px;font-size:12px;font-weight:600;color:var(--accent)}.mc .tu.ext .tp{color:var(--txt-faint)}.mc .tu .puces{margin-top:2px}.mc .tu .puce{padding:2px 7px;font-size:12px}.mc .tu .btn.s{padding:2px 8px;font-size:12px}.mc .grille.v{grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:8px}.mc .grille.v .tu{min-height:124px;padding:10px 10px 8px}.mc .grille.v .tu .gr{font-size:21px}.mc .grille.v .tu .tt{font-size:13px;flex-wrap:wrap;gap:6px}.mc .grille.v .tu .tt svg.i{width:15px;height:15px}.mc .grille.v .tu .tt .pl{font-size:11px;padding:1px 7px}.mc .grille.v .tu .li{flex-wrap:wrap}.mc .grille.v .tu .li .n{white-space:normal}.mc .duo{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:16px;margin-bottom:16px;align-items:start}@media (max-width:560px){.mc .duo{grid-template-columns:1fr}}.mc .duo .paires.un dt{flex-basis:118px}.mc .cass{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;background:color-mix(in srgb,var(--accent) 10%,transparent);border:1px solid color-mix(in srgb,var(--accent) 22%,transparent);border-radius:12px;padding:4px 8px 4px 10px;font-size:13px;color:var(--accent)}.mc .cass b{font-weight:650;margin-right:2px}.mc .cass .puce{font-size:12.5px;padding:3px 9px}.mc .chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.mc .chip{background:transparent;border:1px solid var(--line-strong,var(--line));border-radius:999px;padding:3px 11px;font-size:13px;color:var(--txt-soft)}.mc .chip[aria-pressed=\"true\"]{background:var(--accent);border-color:var(--accent);color:#fff}:root[data-theme=\"dark\"] .mc .chip[aria-pressed=\"true\"]{color:#06231f}.mc .plan{margin:0 0 12px;padding-left:22px;font-size:14px;color:var(--txt-strong,var(--txt));display:grid;gap:6px}.mc .pile{display:flex;height:16px;border-radius:8px;overflow:hidden;background:var(--line);gap:2px}.mc .pile i{display:block;height:100%}.mc .dit{margin:0 0 4px;font-size:14px;color:var(--txt)}.mc pre.jl{margin:0;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 10px;font:11.5px/1.5 \"JetBrains Mono\",ui-monospace,monospace;color:var(--txt);white-space:pre-wrap;word-break:break-word}.mc .cts{display:grid;gap:6px}.mc .ct{background:var(--surface);border:1px solid var(--line);border-radius:13px;overflow:hidden}.mc .ct.ouvert{border-color:color-mix(in srgb,var(--accent) 22%,transparent);background:var(--surface-solid,var(--surface))}.mc .ctl{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1.25fr) minmax(0,1.15fr) 200px 14px;gap:14px;align-items:center;width:100%;text-align:left;background:transparent;border:0;padding:10px 13px}.mc .ctl:hover{background:color-mix(in srgb,var(--accent) 10%,transparent)}.mc .ctl>span{min-width:0;display:flex;flex-direction:column;gap:2px}.mc .ctl b,.mc .ctl .mono{color:var(--txt-strong,var(--txt));overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13.5px}.mc .ctl b{font-weight:650;font-size:14.5px}.mc .ctl small{color:var(--txt-faint);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mc .ctl .c3{flex-direction:row;flex-wrap:wrap;gap:4px 6px;align-items:center}.mc .ctl .c3 small{flex:1 1 100%}.mc .ctl .c4{align-items:flex-end}.mc .ctl .chev{color:var(--txt-faint);transition:transform .2s}.mc .ct.ouvert .ctl .chev{transform:rotate(90deg)}.mc .pc{font:600 12px \"JetBrains Mono\",ui-monospace,monospace;border:1px solid var(--line-strong,var(--line));border-radius:7px;padding:1px 6px;color:var(--txt-strong,var(--txt));background:var(--surface-solid,var(--surface))}.mc .pc.w{border-color:var(--warn);color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent)}.mc .ctf{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:4px 26px;padding:6px 16px 14px;border-top:1px solid var(--line)}.mc .ctf .bloc{min-width:0;padding-top:8px}.mc .ctf h3{font-size:11px;letter-spacing:.8px;text-transform:uppercase;color:var(--txt-faint);margin:0 0 4px;font-weight:650}.mc .ctf h3 .ac{text-transform:uppercase}.mc .ctf table.ptab{font-size:13px}.mc .ctf table.ptab th{font-size:11px;padding:4px 6px}.mc .ctf table.ptab td{padding:5px 6px;font-weight:500;color:var(--txt);white-space:nowrap}.mc .ctf table.ptab td:first-child{font-weight:500}.mc .paires.un{grid-template-columns:1fr}.mc .paires.un div{padding:5px 0;font-size:13.5px}.mc .paires.un dt{flex-basis:104px}.mc .paires.un dd small{display:inline;margin-left:4px}.mc .ctf a,.mc .note a{color:var(--accent);cursor:pointer}@media (max-width:860px){.mc .ctl{grid-template-columns:1fr}.mc .ctl .c4{align-items:flex-start}.mc .ctl .chev{display:none}}.mc .lk{cursor:pointer;background:none;border:0;padding:0;color:var(--txt-soft);font-size:12.5px;text-decoration:underline dotted;text-underline-offset:3px}.mc .lk:hover{color:var(--accent)}.mc .pt{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:4px}.mc .pt.d{background:var(--danger)}.mc .pied{font-size:13px;color:var(--txt-faint);margin:14px 4px 0}.mc .pied a,.mc .fil a{color:var(--accent);cursor:pointer}.mc .grille.v{grid-template-columns:repeat(auto-fit,minmax(128px,1fr))}.mc .grille.v .tu .tt{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:4px 6px}.mc .chemin{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center;font-size:13px;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:6px 10px}.mc .chemin .fl{color:var(--txt-faint);font-size:12px}.mc .ctf .bloc{min-width:0}.mc .chemin{min-width:0}.mc .chemin .mono{min-width:0;overflow-wrap:anywhere;white-space:normal}.mc .ctl.large .nm{grid-column:1/4}.mc .ctl.large .c2,.mc .ctl.large .c3{display:none}.mc .grille.v .tu{container-type:inline-size}@container (max-width:117px){.mc .grille.v .tu .tt{display:block}.mc .grille.v .tu .tt svg.i{display:none}.mc .grille.v .tu .tt .pl{display:inline-flex;margin-top:4px}}.mc .grille.v .tu .tt .pl{grid-column:1/-1;justify-self:start;margin-left:0}.mc .sec>.paires.un dt{flex-basis:160px}";
  // l'état vit hors de la page : elle se redessine à chaque relève
  const S = { page: "vue", d: null, erreur: "", charge: false, q: "", groupe: false, sv: "", svF: "tous", svQ: "", ct: "", pr: "", se: "", tri: "cpu", gestes: null, gestesLus: false, rd: null, hist: { cpu: [], ram: [] }, minuteurs: [], lu: 0 };
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
  const dureeL = (s) => (s == null ? "—" : s >= 172800 ? Math.floor(s / 86400) + " j " + Math.floor((s % 86400) / 3600) + " h" : s >= 7200 ? Math.floor(s / 3600) + " h" : s >= 120 ? Math.floor(s / 60) + " min" : s + " s");
  const mo = (v) => (v == null ? "—" : v >= 1024 ? fr(v / 1024) + " Go" : fr(v, v < 10 ? 1 : 0) + " Mo");
  const jour = (q) => (q && q.length >= 16 ? q.slice(8, 10) + "/" + q.slice(5, 7) + "/" + q.slice(0, 4) + " à " + q.slice(11, 16) : esc(q || "—"));
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
      const tous = d.processus || [], detail = tous.some((p) => p.pid != null), me = d.memoire, r = d.ressources || {}, oom = d.oom, q = S.q.toLowerCase();
      const cle = (p) => String(p.pid != null ? p.pid : p.commande), porteur = (p) => (p.a_qui ? p.a_qui.genre + (p.a_qui.nom ? " " + p.a_qui.nom : "") : "");
      const l = tous.filter((p) => !q || (p.commande + " " + p.utilisateur + " " + porteur(p)).toLowerCase().includes(q)).sort((a, b) => (S.tri === "mem" && detail ? (b.mem_mo || 0) - (a.mem_mo || 0) : b.cpu - a.cpu)).slice(0, detail ? 12 : 99);
      const part = (p) => (me && me.total_mo && p.mem_mo != null ? fr(p.mem_mo / me.total_mo * 100, 1) + " % de la machine" : "");
      const ligne = (p) => {
        const ouvert = S.pr === cle(p), nom = court(p.commande), g = p.a_qui, coul = p.cpu > 50 ? "danger" : p.cpu > 20 ? "warn" : "txt-strong";
        const tete_ = '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl' + (detail ? "" : " large") + '" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="pr" data-n="' + esc(cle(p)) + '"><span class="nm"><b class="mono" title="' + esc(p.commande) + '">' + esc(p.commande) + "</b><small>" +
          esc(p.description || "utilisateur " + p.utilisateur) + "</small></span>" +
          (detail ? '<span class="c2"><span style="font-size:13.5px;color:var(--txt-strong,var(--txt))">' + esc(p.utilisateur) + ' <small style="display:inline">· n° ' + p.pid + "</small></span><small>lancé depuis " + dureeL(p.age_s) + '</small></span><span class="c3">' +
            (g && g.nom ? '<span class="pc">' + esc(g.genre) + " " + esc(g.nom) + "</span>" : "<small>" + esc(g ? g.genre : "") + "</small>") + "</span>" : '<span class="c2"></span><span class="c3"></span>') +
          '<span class="c4"><b class="num" style="font-size:13.5px;color:var(--' + coul + ')">' + fr(p.cpu) + ' %</b><small class="num">' + (detail ? mo(p.mem_mo) : "du processeur") + '</small></span><span class="chev">›</span></button>';
        if (!ouvert) return tete_ + "</div>";
        const lien = g && g.nom && g.genre === "service" ? ' <small><a data-a="aller" data-k="sv" data-n="' + esc(g.nom) + '" data-p="services">ouvrir le service →</a></small>' :
          g && g.nom && g.genre === "conteneur" ? ' <small><a data-a="aller" data-k="ct" data-n="' + esc(g.nom) + '" data-p="conteneurs">ouvrir le conteneur →</a></small>' : "";
        const appartient = !g ? "—" : g.genre === "session" ? "une session ouverte (compte n° " + esc(g.nom) + ")" : g.nom ? esc(g.genre) + ' <span class="mono">' + esc(g.nom) + "</span>" : g.genre === "noyau" ? "le noyau" : "le système";
        return tete_ + '<div class="ctf"><div class="bloc" style="grid-column:1/-1"><h3>' + (p.description ? "Ce que c’est" : "La commande") + "</h3>" + (p.description ? '<p class="dit">' + esc(p.description) + "</p>" : "") +
          '<p class="dit mono" style="font-size:12.5px;' + (p.description ? "color:var(--txt-faint);" : "") + 'word-break:break-all">' + esc(p.commande) + "</p></div>" +
          (detail ? '<div class="bloc"><h3>Identité</h3><dl class="paires un"><div><dt>Numéro (PID)</dt><dd class="mono">' + p.pid + '</dd></div><div><dt>Utilisateur</dt><dd class="mono">' + esc(p.utilisateur) + "</dd></div><div><dt>Lancé depuis</dt><dd>" + dureeL(p.age_s) +
            "</dd></div><div><dt>Appartient à</dt><dd>" + appartient + lien + '</dd></div></dl></div><div class="bloc"><h3>Ce qu’il consomme</h3><dl class="paires un"><div><dt>Processeur</dt><dd><span class="pbar" style="display:inline-block;width:120px;vertical-align:2px;margin-right:8px"><i class="' +
            (p.cpu > 50 ? "d" : p.cpu > 20 ? "w" : "") + '" style="width:' + Math.min(p.cpu, 100) + '%"></i></span>' + fr(p.cpu) + " % <small>en moyenne depuis son lancement</small></dd></div><div><dt>Mémoire</dt><dd>" + mo(p.mem_mo) + (part(p) ? " · " + part(p) : "") + "</dd></div></dl></div>" : "") +
          '<div class="gestes" style="grid-column:1/-1;align-items:center">' + (p.protege ? '<span class="pl w" style="white-space:normal;border-radius:10px;padding:4px 10px">Pas d’arrêt d’ici : ' + esc(p.protege) + "</span>" : "") +
          (g && g.nom && g.genre === "service" ? '<button class="btn s" data-a="aller" data-k="sv" data-n="' + esc(g.nom) + '" data-p="services">Ouvrir son service</button>' : "") + gestesProcessus(p) + '<span style="flex:1"></span>' +
          cass([["Que fait-il ?", "Que fait le processus « " + nom + " »" + (p.pid != null ? " (n° " + p.pid + ")" : "") + " sur la machine ?"],
            ["Est-ce normal ?", "Est-ce normal que « " + nom + " » prenne " + fr(p.cpu) + " % du processeur" + (p.mem_mo != null ? " et " + mo(p.mem_mo) + " de mémoire" : "") + " sur la machine ?"],
            ["Que faire ?", "Le processus « " + nom + " » pèse sur la machine : que me conseilles-tu, sans rien casser ?"]]) + "</div></div></div>";
      };
      let corps;
      if (S.groupe) {
        const g = {}; l.forEach((p) => { g[p.utilisateur] = g[p.utilisateur] || [0, 0, 0]; g[p.utilisateur][0] += p.cpu; g[p.utilisateur][1]++; g[p.utilisateur][2] += p.mem_mo || 0; });
        corps = '<div class="rows">' + Object.keys(g).sort((a, b) => g[b][0] - g[a][0]).map((u) => '<div class="row"><div class="nm"><b class="mono">' + esc(u) + "</b><small>" + g[u][1] + " processus" + (detail ? " · " + mo(g[u][2]) : "") + '</small></div><div class="mil"><span class="pbar"><i class="' +
          (g[u][0] > 50 ? "d" : g[u][0] > 20 ? "w" : "") + '" style="width:' + Math.min(g[u][0], 100) + '%"></i></span><b class="num" style="color:var(--txt-strong,var(--txt))">' + fr(g[u][0]) + ' %</b></div><div class="cote"></div></div>').join("") + "</div>";
      } else corps = '<div class="cts">' + (l.map(ligne).join("") || '<p class="vide">Aucun processus ne correspond.</p>') + "</div>";
      let h = tete("Processus et mémoire", "ce qui tourne sur la machine, et où va la mémoire", age());
      h += sec("Les processus", l.length + " sur " + tous.length + " relevés · relus toutes les 5 s · un clic ouvre la fiche", corps + (detail ? '<p class="note">Le collecteur relève les dix plus gourmands en processeur et les dix plus gourmands en mémoire. Le processeur d’un processus est sa moyenne depuis son lancement.</p>' : ""),
        '<input type="search" placeholder="Filtrer…" aria-label="Filtrer les processus" value="' + esc(S.q) + '" data-s="q" id="mc-q">' + (detail ? '<button class="btn s" data-a="tri">Tri : ' + (S.tri === "mem" ? "mémoire" : "processeur") + "</button>" : "") +
        '<button class="btn s" aria-pressed="' + S.groupe + '" data-a="groupe">' + (S.groupe ? "Un par un" : "Par utilisateur") + "</button>");
      const questions = cass([["Qui prend la mémoire ?", "Qui consomme la mémoire sur la machine en ce moment, et est-ce normal ?"], ["Risque-t-on un plantage ?", "Y a-t-il un risque que des processus soient tués faute de mémoire sur la machine ? Que faire pour l’éviter ?"]]);
      if (me && me.total_mo) {
        const pc = (v) => (v / me.total_mo * 100).toFixed(1), gros = tous.filter((p) => p.mem_mo != null).sort((a, b) => b.mem_mo - a.mem_mo).slice(0, 4);
        h += sec("Où va la mémoire", mo(me.total_mo) + " · " + mo(me.disponible_mo) + " disponibles", '<div class="pile"><i style="width:' + pc(me.applis_mo) + '%;background:var(--accent)" title="programmes"></i><i style="width:' + pc(me.cache_mo) + '%;background:var(--violet,#7c5cfc);opacity:.55" title="cache"></i><i style="width:' +
          pc(me.libre_mo) + '%;background:var(--line-strong,var(--line))" title="libre"></i></div><div class="leg"><span><i style="background:var(--accent);height:10px"></i>programmes ' + mo(me.applis_mo) + '</span><span><i style="background:var(--violet,#7c5cfc);opacity:.55;height:10px"></i>cache ' + mo(me.cache_mo) +
          ' · rendu dès qu’un programme en a besoin</span><span><i style="background:var(--line-strong,var(--line));height:10px"></i>libre ' + mo(me.libre_mo) + "</span>" + (me.echange_total_mo ? "<span>échange " + mo(me.echange_mo) + " sur " + mo(me.echange_total_mo) + "</span>" : "") + "</div>" +
          (gros.length ? '<div class="rows" style="margin-top:12px">' + gros.map((p) => '<div class="row"><div class="nm"><b class="mono">' + esc(court(p.commande)) + "</b><small>" + esc(p.description || porteur(p) || "utilisateur " + p.utilisateur) + '</small></div><div class="mil"><span class="pbar"><i style="width:' +
            Math.min(100, p.mem_mo / me.total_mo * 100).toFixed(1) + '%"></i></span><b class="num" style="color:var(--txt-strong,var(--txt))">' + mo(p.mem_mo) + '</b></div><div class="cote"></div></div>').join("") + "</div>" : ""), questions);
      } else if (r.ram_go && r.ram_go[1]) {
        const tot = r.ram_go[1], pris = r.ram_go[0] || 0;
        h += sec("La mémoire", fr(tot) + " Go", '<div class="pile"><i style="width:' + (pris / tot * 100).toFixed(1) + '%;background:var(--accent)" title="utilisée"></i><i style="width:' + ((tot - pris) / tot * 100).toFixed(1) + '%;background:var(--line-strong,var(--line))" title="disponible"></i></div>' +
          '<div class="leg"><span><i style="background:var(--accent);height:10px"></i>utilisée ' + fr(pris) + ' Go</span><span><i style="background:var(--line-strong,var(--line));height:10px"></i>disponible ' + fr(tot - pris) + " Go, cache compris</span>" +
          (r.swap_go && r.swap_go[1] ? "<span>échange " + fr(r.swap_go[0]) + " sur " + fr(r.swap_go[1]) + " Go</span>" : "") + "</div>", questions);
      }
      h += sec("Tués faute de mémoire", "OOM · les dernières 24 h", oom == null ? '<p class="vide">Inconnu : le collecteur n’a pas répondu.</p>' : oom.length ? '<div class="rows">' + oom.map((o, i) => '<div class="row"><div class="nm"><b class="mono">' + esc(o.processus) + "</b><small>" + esc(String(o.quand).replace("T", " ").slice(0, 16)) +
        '</small></div><div class="mil">occupait <b class="num" style="color:var(--danger)">' + fr(o.mo / 1024) + ' Go</b></div><div class="cote">' + pill("tué par le noyau", "d") + demande("Pourquoi ?", "Pourquoi " + o.processus + " a-t-il été tué faute de mémoire sur la machine, et comment éviter que cela recommence ?") +
        '<button class="btn s" data-a="acquitter" data-i="' + i + '">Acquitter</button></div></div>').join("") + "</div>" : '<p class="vide">Aucun processus tué faute de mémoire.</p>',
        (oom && oom.length ? '<button class="btn s" data-a="acquitter" data-i="tous">Tout acquitter</button>' : "") + demande("Demander", "Y a-t-il eu des processus tués faute de mémoire récemment sur la machine, et pourquoi ?"));
      return h + blocGestes();
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
          (s.ports.length ? s.ports.map((p) => '<span class="pc">' + esc(p) + "</span>").join("") : "<small>aucun port</small>") + '</span><span class="c4">' + pill(mot[0], mot[1]) + '<small class="num">' + (s.etat === "actif" && s.memoire_mo != null ? (s.cpu != null ? fr(s.cpu) + " % · " : "") + mo(s.memoire_mo) : esc(s.sous_etat)) + '</small></span><span class="chev">›</span></button>' +
          (ouvert ? '<div class="ctf"><div class="bloc" style="grid-column:1/-1"><h3>Ce que c’est</h3><p class="dit">' + esc(s.description || s.systemd || "—") + "</p>" + (s.systemd && s.description ? '<p class="dit" style="color:var(--txt-faint);font-size:12.5px">systemd : ' + esc(s.systemd) + "</p>" : "") + "</div>" +
            '<div class="bloc"><h3>État</h3><dl class="paires un"><div><dt>État</dt><dd>' + pill(mot[0], mot[1]) + " " + esc(s.sous_etat) + (s.depuis && s.etat === "actif" ? " <small>depuis le " + jour(s.depuis) + "</small>" : "") + "</dd></div><div><dt>Au démarrage</dt><dd>" +
            (s.au_demarrage ? "se lance avec la machine" : "ne se lance pas avec la machine") + boutonDemarrage(s) + "</dd></div><div><dt>Processus</dt><dd>" + (s.etat === "actif" && (s.pid || s.memoire_mo != null) ? [s.pid ? 'n° <span class="mono">' + s.pid + "</span>" : "", s.cpu != null ? "processeur " + fr(s.cpu) + " %" : "", s.memoire_mo != null ? "mémoire " + mo(s.memoire_mo) : ""].filter(Boolean).join(" · ") +
              (s.redemarrages ? " <small>" + s.redemarrages + " relance" + (s.redemarrages > 1 ? "s" : "") + " par systemd</small>" : "") : "—") + "</dd></div><div><dt>Écoute sur</dt><dd>" +
            (s.ports.length ? s.ports.map((p) => '<span class="pc">' + esc(p) + "</span>").join(" ") + ' <small><a data-a="module" data-e="securite" data-v="exposition" data-ou="Sécurité › Exposition">qui peut les joindre →</a></small>' : "aucun port") + "</dd></div>" +
            ((s.noms || []).length ? "<div><dt>Noms publics</dt><dd>" + s.noms.map((n) => '<span class="mono">' + esc(n) + "</span>").join(", ") + "</dd></div>" : "") + "</dl></div>" +
            '<div class="bloc"><h3>Si on l’arrête</h3><p class="dit">' + esc(s.si_arret || "Ce que ce service porte n’est pas décrit ici : demande-le à Cassandra avant d’y toucher.") + "</p>" + (s.protege ? '<p class="dit" style="color:var(--warn)">' + esc(s.protege) + "</p>" : "") +
            ((s.journal || []).length ? '<h3 style="margin-top:10px">Dernières lignes du journal</h3><pre class="jl">' + s.journal.map(esc).join("\n") + "</pre>" : "") + "</div>" +
            '<div class="gestes" style="grid-column:1/-1;align-items:center">' + gestesService(s) +
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
      return h + blocGestes();
    },
    conteneurs() {
      const d = D(), ct = d.conteneurs;
      if (ct == null) return tete("Conteneurs", "Docker sur la machine", age()) + inconnu("Les conteneurs");
      const ko = ct.filter((c) => !c.tourne).length, pub = ct.filter((c) => (c.ports || []).some((p) => p.niveau !== "ok")).length, noms = ct.filter((c) => (c.proxys || []).length).length, releve = ct.some((c) => c.releve);
      const port = (p) => '<span class="pc ' + (p.niveau === "ok" ? "" : "w") + '" title="' + esc(p.hote) + ":" + p.port + " → " + p.interne + "/" + esc(p.proto) + ' dans le conteneur">' + p.port + "/" + esc(p.proto) + "</span>";
      const p2 = (dt, dd) => "<div><dt>" + dt + "</dt><dd>" + dd + "</dd></div>";
      const fiche = (c) => {
        const ports = c.ports || [], px = c.proxys || [], vol = c.volumes || [], cert = px.find((x) => x.cert_j != null);
        const image = '<div class="bloc"><h3>Image</h3><dl class="paires un">' + p2("Image", '<span class="mono">' + esc(c.image) + "</span>") + (c.releve ? p2("Distribution", esc(c.distribution || "non lue : l’image n’a pas de fichier de version lisible")) : "") +
          p2("Construite", (c.image_age_j != null ? "il y a " + c.image_age_j + " jour" + (c.image_age_j > 1 ? "s" : "") : "—") + (c.taille_mo ? " · " + mo(c.taille_mo) : "")) +
          p2("Failles connues", '<a data-a="module" data-e="securite" data-v="outils" data-ou="Sécurité › Outils (Trivy)">Sécurité › Outils →</a>') + "</dl></div>";
        const marche = '<div class="bloc"><h3>Marche</h3><dl class="paires un">' + p2("État", esc(c.etat)) + p2("Ressources", c.tourne && c.cpu != null ? "processeur " + fr(c.cpu, 2) + " % · mémoire " + esc(c.memoire) : "—") +
          (c.releve ? p2("Santé", esc(c.sante)) + p2("Redémarrage", "politique « " + esc(c.politique || "no") + " » · " + c.redemarrages + " redémarrage" + (c.redemarrages > 1 ? "s" : "")) : "") + "</dl></div>";
        if (!c.releve) return '<div class="ctf">' + image + marche + '<p class="note" style="grid-column:1/-1">Les ports, le réseau et les volumes de ce conteneur ne sont pas encore relevés.</p>';
        return '<div class="ctf"><div class="bloc"><h3>Ports</h3>' + (ports.length ? '<table class="ptab"><thead><tr><th>Sur la machine</th><th>Dans le conteneur</th><th>Qui peut le joindre</th></tr></thead><tbody>' +
            ports.map((p) => '<tr><td class="mono">' + esc(p.hote) + ":" + p.port + '</td><td class="mono">' + p.interne + "/" + esc(p.proto) + "</td><td>" + pill(p.portee, p.niveau) + "</td></tr>").join("") +
            '</tbody></table><p class="note"><a data-a="module" data-e="securite" data-v="exposition" data-ou="Sécurité › Exposition">Sécurité › Exposition →</a> dit qui joint chaque port de la machine ; ici, à quel conteneur il appartient.</p>' :
            '<p class="vide">Aucun port publié' + (String(c.reseau).startsWith("host") ? " : ce conteneur partage le réseau de la machine, ses ports sont ceux de la machine." : ".") + "</p>") + "</div>" +
          '<div class="bloc"><h3>Reverse proxy</h3>' + (px.length ? '<div class="rows">' + px.map((x) => '<div class="chemin"><span class="mono"><b>' + esc(x.nom) + "</b>" + esc(x.chemin === "/" ? "" : " " + x.chemin.replace(/^~\*? \^?/, "")) + '</span><span class="fl">→ nginx' + (x.genre === "grpc" ? " (gRPC)" : "") +
            ' →</span><span class="mono">' + esc(x.vers) + '</span><span class="fl">→</span><span class="mono">' + esc(c.nom) + "</span></div>").join("") + "</div>" +
            (cert ? '<dl class="paires un">' + p2("Certificat", cert.cert_j + ' jours restants <small><a data-a="module" data-e="certificats" data-v="" data-ou="Sécurité › Certificats">Certificats →</a></small>') + "</dl>" : "") :
            '<p class="vide">Aucun nom public ne mène à ce conteneur : il n’est joint que depuis la machine' + (ports.some((p) => p.niveau !== "ok") ? ", ou directement par ses ports ouverts" : "") + ".</p>") + "</div>" + image + marche +
          '<div class="bloc"><h3>Réseau et volumes</h3><dl class="paires un">' + p2("Réseau", esc(c.reseau || "—") + (c.ip ? ' · <span class="mono">' + esc(c.ip) + "</span>" : "")) +
          p2("Volumes", vol.length ? vol.map((v) => '<span class="mono">' + esc(v.source) + '</span> → <span class="mono">' + esc(v.cible) + '</span> <small style="display:inline">' + esc(v.genre === "bind" ? "dossier de la machine" : v.genre) + "</small>").join("<br>") : "aucun : rien n’est gardé si le conteneur est recréé") +
          p2("Posé par", esc(c.compose || "conteneur seul (aucun fichier compose)")) + "</dl></div>";
      };
      const ligne = (c) => {
        const ouvert = S.ct === c.nom, coul = c.pause ? "w" : c.tourne ? "ok" : "d", charge = c.tourne && !c.pause && c.cpu != null ? fr(c.cpu, 2) + " % · " + c.memoire : "—", ports = c.ports || [], px = c.proxys || [];
        return '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="ct" data-n="' + esc(c.nom) + '"><span class="nm"><b class="mono">' + esc(c.nom) + "</b><small>" + esc(c.role || "conteneur Docker") + '</small></span><span class="c2"><span class="mono">' + esc(c.image) +
          "</span><small>" + esc(c.distribution || (c.image_age_j != null ? "image construite il y a " + c.image_age_j + " j" : "")) + '</small></span><span class="c3">' + (ports.length ? ports.map(port).join("") : c.releve ? "<small>aucun port publié</small>" : "") +
          (px.length ? "<small>↳ " + esc(px.map((x) => x.nom).filter((n, i, t) => t.indexOf(n) === i).join(", ")) + "</small>" : "") + '</span><span class="c4">' + pill(c.etat, coul) + '<small class="num">' + esc(charge) + '</small></span><span class="chev">›</span></button>' +
          (ouvert ? fiche(c) + '<div class="gestes" style="grid-column:1/-1;align-items:center">' + gestesConteneur(c) + '<span style="flex:1"></span>' +
            cass([["Que fait-il ?", "Que fait le conteneur " + c.nom + " sur la machine ?"], ["Faire le point", "Fais-moi le point sur le conteneur " + c.nom + " de la machine : ce qu’il fait, ses ports, son image, ce qui cloche."]]) + "</div></div>" : "") + "</div>";
      };
      return tete("Conteneurs", (ct.length - ko) + " sur " + ct.length + " tournent" + (releve ? " · " + pub + " avec un port ouvert au-delà de la machine · " + noms + " derrière un nom public" : ""), age()) +
        sec("Les conteneurs", "Docker · un clic ouvre la fiche", ct.length ? '<div class="cts">' + ct.map(ligne).join("") + "</div>" + (releve ? '<p class="note">Sur chaque ligne : le nom et son rôle, l’image et sa distribution, les ports publiés (en orange : ouverts au-delà de la machine) et le nom public qui y mène, l’état et la charge.</p>' : "") :
          '<p class="vide">Aucun conteneur sur cette machine.</p>', '<button class="btn s" data-a="module" data-e="securite" data-v="outils" data-ou="Sécurité › Outils (Trivy)" title="Les failles connues dans les images">Failles des images</button>') + blocGestes();
    },
    sessions() {
      const d = D(), se = d.sessions, rf = d.refus, cx = d.connexions;
      if (se == null) return tete("Sessions", "qui est connecté à la machine", age()) + inconnu("Les sessions");
      const p2 = (dt, dd) => "<div><dt>" + dt + "</dt><dd>" + dd + "</dd></div>";
      const ligne = (s, i) => {
        const k = s.utilisateur + "@" + s.adresse, ouvert = S.se === k, quoi = s.anonyme ? "Connexion SSH pas encore identifiée" : s.type === "ftp" ? "Dépôt de fichiers par FTP" : "Session SSH de " + s.utilisateur;
        const lecture = s.anonyme ? "L’utilisateur « sshd » veut dire que personne n’est encore entré : quelqu’un frappe à la porte. Le plus souvent, c’est une tentative automatique, qui sera refusée." :
          s.reseau === "Tailscale" ? "Une session ouverte depuis une machine de ton réseau privé" + (s.cle ? ", avec une clé." : ".") : s.reseau === "Internet" ? "Une session ouverte depuis Internet." : "Une session ouverte depuis " + s.reseau + ".";
        const connue = !s.anonyme && /^\d+ connexion/.test(s.connu || "") && !s.refus_1h;
        const mot = s.anonyme ? ["pas identifiée", "w"] : connue ? ["connue", "ok"] : s.reseau === "Tailscale" ? ["réseau privé", "ok"] : ["à regarder", ""];
        return '<div class="ct ' + (ouvert ? "ouvert" : "") + '"><button class="ctl" aria-expanded="' + ouvert + '" data-a="ouvrir" data-k="se" data-n="' + esc(k) + '"><span class="nm"><b class="mono">' + esc(s.utilisateur) + "</b><small>" + esc(quoi) + '</small></span><span class="c2"><span class="mono">' + esc(s.adresse) +
          "</span><small>" + esc(s.reseau) + (s.machine ? " · la machine " + esc(s.machine) : "") + '</small></span><span class="c3" style="flex-direction:column;align-items:flex-start"><span style="font-size:13.5px;color:var(--txt-strong,var(--txt))">depuis ' + esc(s.depuis) + "</span><small>" + esc(s.type.toUpperCase()) +
          (s.inactivite ? " · inactive depuis " + esc(s.inactivite) : "") + '</small></span><span class="c4">' + pill(mot[0], mot[1]) + "<small>" + esc(s.methode ? s.methode + (s.cle ? " " + s.cle.replace(/^\S+ /, "") : "") : "") + '</small></span><span class="chev">›</span></button>' +
          (ouvert ? '<div class="ctf"><div class="bloc" style="grid-column:1/-1"><h3>Ce que c’est</h3><p class="dit">' + esc(lecture) + '</p></div><div class="bloc"><h3>D’où elle vient</h3><dl class="paires un">' + p2("Adresse", '<span class="mono">' + esc(s.adresse) + "</span>") + p2("Réseau", esc(s.reseau)) +
            (s.machine ? p2("Machine", esc(s.machine)) : "") + (s.connu ? p2("Déjà vue", esc(s.connu)) : "") + '</dl></div><div class="bloc"><h3>Comment elle est entrée, ce qu’elle fait</h3><dl class="paires un">' +
            p2("Identification", esc(s.methode ? s.methode + (s.cle ? " · " + s.cle : "") : s.anonyme ? "aucune pour l’instant" : "—")) + p2("Ouverte", esc(s.depuis) + " <small>heure du serveur</small>") + p2("Terminal", '<span class="mono">' + esc(s.terminal || "—") + "</span>") +
            p2("Inactive depuis", esc(s.inactivite || "—")) + p2("En cours", '<span class="mono">' + esc(s.commande || (s.anonyme ? "en attente d’identification" : "—")) + "</span>") +
            '</dl></div><div class="gestes" style="grid-column:1/-1;align-items:center"><button class="btn s d" data-a="deconnecter" data-i="' + i + '">Déconnecter</button>' + (s.reseau === "Internet" ? '<button class="btn s d" data-a="bannir" data-i="' + i + '">Bannir l’adresse</button>' : "") + '<span style="flex:1"></span>' +
            cass([["Qui est-ce ?", "Qui se cache derrière la session " + s.utilisateur + " depuis " + s.adresse + " sur la machine ?"], ["Est-ce normal ?", "La session " + s.utilisateur + " depuis " + s.adresse + " sur la machine est-elle normale ? Que me conseilles-tu ?"],
              ["Qu’a-t-elle fait ?", "Qu’a fait la session " + s.utilisateur + " depuis " + s.adresse + " sur la machine depuis son ouverture ?"]]) + "</div></div>" : "") + "</div>";
      };
      let h = tete("Sessions", "qui est connecté à la machine · " + se.length + " ouverte" + (se.length > 1 ? "s" : "") + (rf && rf.total != null ? " · " + rf.total + " tentatives refusées dans l’heure" : ""), age());
      h += sec("Sessions ouvertes", "un clic ouvre la fiche", se.length ? '<div class="cts">' + se.map(ligne).join("") + "</div>" : '<p class="vide">Aucune session ouverte.</p>', (se.some((s) => !s.anonyme) ? '<button class="btn s d" data-a="dehors">Tout le monde dehors</button>' : "") + '<button class="btn s" data-a="module" data-e="securite" data-v="acces" data-ou="Sécurité › Accès">Sécurité › Accès</button>');
      if (rf) {
        const max = Math.max.apply(null, rf.adresses.map((a) => a[1]).concat([1]));
        h += sec("Tentatives refusées", esc(rf.texte.split(" · ")[0]), rf.adresses.length ? '<div class="rows">' + rf.adresses.map((a) => '<div class="row"><div class="nm"><b class="mono">' + esc(a[0]) + "</b><small>" + a[1] + ' tentatives en une heure</small></div><div class="mil"><span class="pbar"><i class="w" style="width:' +
          Math.round(a[1] / max * 100) + '%"></i></span></div><div class="cote"><button class="btn s d" data-a="bannir" data-ip="' + esc(a[0]) + '">Bannir</button></div></div>').join("") + "</div>" : '<p class="vide">' + esc(rf.texte) + "</p>",
          '<button class="btn s" data-a="module" data-e="securite" data-v="defenses" data-ou="Sécurité › Défenses">Sécurité › Défenses</button>' + cass([["Est-on attaqué ?", "Y a-t-il une attaque en cours sur le SSH de la machine ? Que me conseilles-tu ?"]]));
      }
      if (cx != null) {
        h += sec("Connexions réussies", "les trente derniers jours · par compte, adresse et clé", cx.length ? '<div class="rows">' + cx.map((x) => '<div class="row"><div class="nm"><b class="mono">' + esc(x.utilisateur) + "</b><small>" + esc(x.reseau) + (x.machine ? " · " + esc(x.machine) : "") + ' · <span class="mono">' + esc(x.adresse) +
          '</span></small></div><div class="mil" style="flex-direction:column;align-items:flex-start;gap:1px"><span>dernière le ' + jour(x.derniere) + '</span><small style="color:var(--txt-faint);font-size:12.5px">' + esc(x.methode + (x.cle ? " · " + x.cle : "")) + '</small></div><div class="cote"><span class="num" style="font-size:13px;color:var(--txt-soft,var(--txt))">' +
          x.nombre + " fois</span></div></div>").join("") + '</div><p class="note">Lu dans le journal de sshd : qui est entré, d’où et avec quelle clé. D’une clé, la page ne montre que le commentaire.' + ((d.voisins || []).some((v) => v.cle === "tailscale") ? " Les connexions ouvertes par Tailscale SSH n’y figurent pas : elles ne passent pas par sshd." : "") + "</p>" : '<p class="vide">Aucune connexion réussie relevée sur trente jours.</p>',
          cass([["Rien d’anormal ?", "Regarde les connexions SSH réussies des trente derniers jours sur la machine : y en a-t-il une qui ne me ressemble pas ?"]]));
      }
      return h + blocGestes();
    },
    fiche() {
      const d = D(), m = d.machine || {}, r = d.ressources || {}, lg = d.logiciels || { installes: [], absents: [] }, mt = m.materiel || null, vs = lg.versions || {}, cpu = (mt && mt.cpu) || {};
      const virtuelle = m.nature && m.nature !== "none", publique = mt && mt.ip_publique, portee = publique && (m.interfaces || []).find((i) => i.v4.indexOf(publique) >= 0);
      const depuisLe = (q) => { if (!q || q.length < 10) return ""; const j = Math.floor((Date.now() - new Date(q.slice(0, 10) + "T00:00:00").getTime()) / 86400000); return isNaN(j) || j < 0 ? "" : j < 60 ? "il y a " + j + " jour" + (j > 1 ? "s" : "") : "il y a " + Math.floor(j / 30.4) + " mois"; };
      const leJour = (q) => (q && q.length >= 10 ? q.slice(8, 10) + "/" + q.slice(5, 7) + "/" + q.slice(0, 4) : "");
      if (muet() || !m.nom) return tete("La fiche de la machine", "ce qu’elle est", age()) + inconnu("La fiche de la machine");
      const p = (dt, dd) => "<div><dt>" + dt + "</dt><dd>" + dd + "</dd></div>";
      const bloc = (t, meta, corps, droite) => sec(t, meta, corps, droite).replace('class="carte sec"', 'class="carte sec" style="margin:0"');
      const texte = ["Machine : " + m.nom, "Système : " + [m.os, m.archi, m.nature].filter(Boolean).join(" · "), "Noyau : " + m.noyau, cpu.modele ? "Processeur : " + cpu.modele + (cpu.coeurs ? " · " + cpu.coeurs + " cœurs" : "") : "", r.ram_go ? "Mémoire : " + fr(r.ram_go[1]) + " Go" : "", "Adresses : " + (m.interfaces || []).map((i) => (i.v4[0] || i.v6[0] || "?") + " (" + i.nom + ")").join(", "), "Allumée depuis : " + m.allumee].filter(Boolean).join("\n");
      let h = tete("La fiche de la machine", "ce qu’elle est, ce qu’elle porte", age());
      const rd = S.rd || {}, rt = rd.retour, pasRevenus = rt ? (rt.pas_revenus.services || []).map((x) => "service " + x).concat((rt.pas_revenus.conteneurs || []).map((x) => "conteneur " + x)) : [];
      if (rt) h += '<section class="carte sec bandeau-v"><div class="verdict"><div class="vm ' + (pasRevenus.length ? "w" : "") + '"></div><div style="flex:1;min-width:0"><p class="vt">La machine est revenue le ' + jour(rt.revenue) + '</p><p class="vs">Coupure d’environ ' +
        duree(rt.coupure_s) + ". " + (pasRevenus.length ? "Ne sont pas revenus : " + esc(pasRevenus.join(", ")) + "." : "Tout ce qui tournait avant est revenu.") + '</p><div class="gestes"><button class="btn s" data-a="retourLu">Vu</button>' +
        (pasRevenus.length ? '<button class="btn s p" data-a="page" data-p="services">Voir les services</button>' : "") + "</div></div></div></section>";
      h += '<section class="carte sec bandeau-v"><div class="verdict"><div class="vm ' + (m.redemarrage ? "d" : "") + '"></div><div style="flex:1;min-width:0"><p class="vt mono" style="font-size:22px">' + esc(m.nom) + '</p><div class="puces" style="margin-top:8px">' +
        [m.os, m.nature && "nature : " + m.nature, cpu.coeurs && cpu.coeurs + " cœurs", r.ram_go && r.ram_go[1] && fr(r.ram_go[1]) + " Go de mémoire", r.disque_go && r.disque_go[1] && fr(r.disque_go[1], 0) + " Go de disque", m.allumee && "allumée depuis " + m.allumee].filter(Boolean).map((x) => '<span class="puce">' + esc(x) + "</span>").join("") +
        (m.redemarrage ? '<span class="puce" style="border-color:var(--danger);color:var(--danger)">redémarrage requis</span>' : "") +
        (rd.prevu ? '<span class="puce" style="border-color:var(--info,var(--accent));color:var(--info,var(--accent))">redémarrage prévu le ' + jour(rd.prevu) + ' <button class="lk" style="margin-left:6px" data-a="annulerRedemarrage">annuler</button></span>' : "") +
        '</div></div><div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end"><span style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end"><button class="btn s" data-a="copier" data-t="' + esc(texte) + '">Copier la fiche</button>' +
        '<button class="btn s ' + (m.redemarrage ? "d" : "") + '" data-a="redemarrer">Redémarrer la machine</button></span>' +
        cass([["Présente-la-moi", "Présente-moi la machine " + m.nom + " : ce qu’elle est, ce qu’elle porte, ce qui mérite mon attention."], ["Est-elle assez grande ?", "La machine " + m.nom + " est-elle bien dimensionnée pour ce qu’elle porte (processeur, mémoire, disque) ?"]]) + "</div></div></section>";
      h += '<div class="duo">';
      h += bloc("Identité", "qui elle est", '<dl class="paires un">' + p("Nom", '<span class="mono">' + esc(m.nom) + "</span>") + p("Système", esc(m.os) + (m.archi ? " <small>" + esc(m.archi) + "</small>" : "")) + (m.nature ? p("Nature", esc(m.nature === "none" ? "machine physique" : "machine virtuelle (" + m.nature + ")")) : "") +
        (mt && mt.constructeur ? p(virtuelle ? "Hébergeur" : "Constructeur", esc(mt.constructeur) + (virtuelle ? " <small>d’après le matériel que la machine virtuelle déclare</small>" : "")) : "") +
        (mt && mt.installee ? p("Installée", "le " + leJour(mt.installee) + (depuisLe(mt.installee) ? " <small>" + depuisLe(mt.installee) + "</small>" : "")) : "") +
        p("Noyau", '<span class="mono">' + esc(m.noyau || "—") + "</span>") + p("Allumée depuis", esc(m.allumee || "—") + (mt && mt.demarree ? " <small>dernier démarrage le " + jour(mt.demarree) + "</small>" : "")) + p("Redémarrage", (rd.prevu ? '<span style="color:var(--info,var(--accent))">prévu le ' + jour(rd.prevu) + '</span> <button class="lk" data-a="annulerRedemarrage">annuler</button>' :
          m.redemarrage ? '<span style="color:var(--danger)">requis</span> <small>' + esc(m.redemarrage_texte) + "</small>" : "pas de redémarrage requis") +
          (rd.prevu ? "" : ' <button class="btn s ' + (m.redemarrage ? "d" : "") + '" style="margin-left:6px" data-a="redemarrer">Redémarrer…</button>')) + "</dl>");
      h += bloc("Matériel", "ce qu’elle a", '<dl class="paires un">' + (cpu.modele || cpu.fils ? p("Processeur", esc(cpu.modele || "modèle non déclaré") + " <small>" + [cpu.coeurs && cpu.coeurs + " cœur" + (cpu.coeurs > 1 ? "s" : ""), cpu.fils && cpu.fils + " fil" + (cpu.fils > 1 ? "s" : ""), cpu.mhz && fr(cpu.mhz / 1000, 1) + " GHz"].filter(Boolean).join(" · ") + "</small>") : "") + p("Mémoire", r.ram_go && r.ram_go[1] ? fr(r.ram_go[1]) + " Go <small>" + fr(r.ram_go[0]) + " Go utilisés</small>" : "—") + p("Échange", r.swap_go && r.swap_go[1] ? fr(r.swap_go[1]) + " Go <small>" + fr(r.swap_go[0]) + " Go utilisés</small>" : "aucun") +
        p("Disque", r.disque_go && r.disque_go[1] ? fr(r.disque_go[1], 0) + " Go <small>" + fr(r.disque_go[0], 0) + " Go utilisés</small>" : "—") +
        (mt ? p("Température", mt.temperature ? fr(mt.temperature, 0) + " °C au plus chaud" : virtuelle ? "non relevée : une machine virtuelle n’a pas de sonde" : "non relevée") +
          (mt.carte ? p("Carte mère", esc(mt.carte) + (mt.bios ? " <small>BIOS " + esc(mt.bios) + "</small>" : "") + (virtuelle ? " <small>celle que l’hébergeur simule</small>" : "")) : "") +
          (mt.disques || []).map((x) => p("Disque " + esc(x[0]), esc(x[1] || "modèle non déclaré") + " · " + esc(String(x[2]).replace(/^([\d.]+)([KMGT])$/, (_, n, u) => fr(+n) + " " + u + "o")) + " <small>" + esc(x[3]) + "</small>")).join("") : "") + "</dl>", '<button class="btn s" data-a="page" data-p="ressources">Ressources</button>');
      h += bloc("Stockage", "où sont les fichiers", '<div class="rows">' + (d.disques || []).map((x) => '<div class="row" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)"><div class="nm"><b class="mono">' + esc(x.montage) + "</b><small>" + (x.type ? esc(x.type) + " · " : "") + fr(x.utilise_go) + " sur " + fr(x.total_go) + " Go" +
        (x.inodes_pct != null ? " · inodes " + x.inodes_pct + " %" : "") + '</small></div><div class="mil" style="flex-direction:column;align-items:flex-start;gap:3px"><span style="display:flex;align-items:center;gap:8px;width:100%"><span class="pbar"><i class="' + niv(x.pct) + '" style="width:' + (x.pct || 0) +
        '%"></i></span><b class="num" style="color:var(--txt-strong,var(--txt))">' + (x.pct == null ? "—" : x.pct + " %") + '</b></span><small style="color:var(--' + (x.alerte ? "danger" : "txt-faint") + ');font-size:12.5px">' + esc(x.prevision.split(" (")[0]) + "</small></div></div>").join("") + "</div>",
        '<button class="btn s" data-a="module" data-e="historique" data-v="" data-ou="Historique › Prévision du disque">Prévision</button>');
      h += bloc("Réseau", "comment on la joint", '<div class="rows">' + (m.interfaces || []).map((i) => '<div class="row" style="grid-template-columns:minmax(0,.7fr) minmax(0,1.6fr) auto"><div class="nm"><b class="mono">' + esc(i.nom) + "</b><small>" + esc(i.etat) +
        '</small></div><div class="mil" style="flex-direction:column;align-items:flex-start;gap:1px"><span class="mono" style="color:var(--txt-strong,var(--txt))">' + esc(i.v4.join(", ") || "—") + '</span><small class="mono" style="color:var(--txt-faint);font-size:12px">' + esc(i.v6.join(", ")) + '</small></div><div class="cote">' +
        (i.defaut ? pill("route par défaut", "i") : "") + "</div></div>").join("") + '</div><dl class="paires un" style="margin-top:8px">' + (mt && mt.passerelle ? p("Passerelle", '<span class="mono">' + esc(mt.passerelle) + "</span>") : "") +
        (publique ? p("Vue de dehors", '<span class="mono">' + esc(publique) + "</span>" + (portee ? " <small>la même que " + esc(portee.nom) + " : pas de box devant</small>" : " <small>une autre que ses interfaces : une box ou un relais est devant</small>")) : "") +
        (mt && mt.inverse ? p("Nom inverse", '<span class="mono">' + esc(mt.inverse) + "</span>") : "") + p("Résolution DNS", esc(m.dns || "—")) + "</dl>", '<button class="btn s" data-a="module" data-e="securite" data-v="exposition" data-ou="Sécurité › Exposition">Exposition</button>');
      h += bloc("Horloge", "l’heure qu’elle croit", '<dl class="paires un">' + p("Synchronisation", esc(m.horloge || "—")) + p("Fuseau", '<span class="mono">' + esc(m.fuseau || "—") + "</span> <small>les heures de Cassandra sont celles du serveur</small>") + "</dl>");
      h += bloc("Protections de base", "résumé ici · réglé dans Sécurité", '<dl class="paires un">' + (m.pare_feu || []).map((x, i) => p("Pare-feu" + (i ? " (IPv6)" : ""), esc(x) + (!i && mt && mt.pare_feu_entree ? " <small>ce qu’aucune règle ne nomme : " + esc(mt.pare_feu_entree) + "</small>" : ""))).join("") + p("Mises à jour", esc((m.maj || {}).texte || "—")) +
        (mt && mt.maj_auto ? p("Automatiques", esc(mt.maj_auto)) : "") + (m.taches ? p("Tâches planifiées", esc(m.taches)) : "") + "</dl>",
        '<button class="btn s" data-a="module" data-e="securite" data-v="maj" data-ou="Sécurité › Mises à jour et noyau">Mises à jour</button><button class="btn s" data-a="module" data-e="securite" data-v="parefeu" data-ou="Sécurité › Pare-feu">Pare-feu</button>');
      h += "</div>";
      h += sec("Logiciels installés", lg.installes.length + " trouvés · " + lg.absents.length + " cherchés et absents", '<div class="puces">' + lg.installes.map((x) => '<span class="puce"><span class="mono">' + esc(x) + "</span>" + (vs[x] ? " <b>" + esc(vs[x]) + "</b>" : "") + "</span>").join("") + "</div>" +
        (lg.absents.length ? '<p class="note" style="margin-top:10px">Cherchés et absents : ' + lg.absents.map((x) => '<span class="mono">' + esc(x) + "</span>").join(", ") + ".</p>" : ""), cass([["Que mettre à jour ?", "Quels logiciels de la machine " + m.nom + " sont en retard d’une version importante ou en fin de vie, et par quoi commencer ?"]]));
      if ((d.cassandra || []).length) h += sec("Cassandra sur cette machine", "ce qu’elle y a posé", '<dl class="paires un">' + d.cassandra.map((x) => { const t = x.titre.replace(/^[^—]+— /, ""); return p(esc(t.charAt(0).toUpperCase() + t.slice(1)), esc(x.texte)); }).join("") + "</dl>",
        '<button class="btn s" data-a="page" data-p="services">Ses services</button>');
      return h + blocGestes();
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
    try { const d = await agir("vue.machine"); if (d && d.ok === false) { S.d = null; S.erreur = d.raison || "lecture refusée"; } else { S.d = d; S.erreur = ""; S.lu = Date.now(); noterMesure(); appliquerFrais(); } }
    catch (e) { S.erreur = (e && e.message) || "la lecture a échoué"; if (!S.d) S.d = null; }
    S.charge = false; rendre();
    const avant = JSON.stringify(S.gestes); chargerGestes().then(() => { if (JSON.stringify(S.gestes) !== avant && S.page !== "vue" && !document.querySelector(".kit-m")) rendre(); });
  }
  // Toutes les cinq secondes : les mesures seules (une lecture légère), posées dans les tuiles sans redessiner la page.
  async function battre() {
    if (!visible() || !S.d || muet()) return;
    let m; try { m = await agir("sensorium.metriques"); } catch (e) { return; }
    if (!m || m.muet || !S.d.ressources) return;
    const r = S.d.ressources, n = (k) => (typeof m[k] === "number" ? m[k] : null);
    Object.assign(r, { cpu: n("cpu"), ram: n("ram"), swap: n("swap"), disque: n("disk"), charge: [n("load_1m"), n("load_5m"), n("load_15m")], ram_go: [n("ram_used_gb"), n("ram_total_gb")], swap_go: [n("swap_used_gb"), n("swap_total_gb")], disque_go: [n("disk_used_gb"), n("disk_total_gb")], disque_libre_go: n("disk_free_gb") });
    const avant = {}; (S.d.processus || []).forEach((p) => { if (p.pid != null) avant[p.pid + "|" + p.commande] = p; });
    const liste = Array.isArray(m.processes) && m.processes.length ? m.processes : m.top_processes;
    if (Array.isArray(liste)) S.d.processus = liste.map((p) => { const c = String(p.command || p.name || "?"), a = avant[p.pid + "|" + c] || {};
      return { utilisateur: String(p.user || ""), cpu: typeof p.cpu === "number" ? p.cpu : 0, commande: c, pid: typeof p.pid === "number" ? p.pid : null, mem_mo: typeof p.mem_mb === "number" ? p.mem_mb : null, age_s: typeof p.age_s === "number" ? p.age_s : null,
        a_qui: p.genre ? { genre: String(p.genre), nom: String(p.a_qui || "") } : null, description: a.description || "", protege: a.protege || "" }; });
    if (m.memory && m.memory.total_mo) S.d.memoire = m.memory;
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
  function page(p) { S.page = PAGES[p] ? p : "vue"; rendre(); if (S.page === "fiche") chargerRd(); const t = document.getElementById("tab-overview"); if (t) t.scrollTop = 0; if (R) R.scrollTop = 0; }

  // ───────────────────────── les gestes (ceux qui existent déjà)
  function feuille(titre, html) {
    const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
    const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.style.width = "min(760px,calc(100% - 32px))";
    m.innerHTML = "<h2>" + esc(titre) + "</h2>" + html + '<div class="acts"><button class="btn pri" data-c="fermer">Fermer</button></div>';
    const clore = () => { v.remove(); m.remove(); };
    v.addEventListener("click", clore); m.addEventListener("click", (e) => { if (e.target.closest("[data-c]")) clore(); }); m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(); });
    document.body.appendChild(v); document.body.appendChild(m); m.querySelector("[data-c]").focus();
  }
  // ───────────────────────── les gestes du lot 3 : services, conteneurs, processus, adresses, redémarrage — chacun confirmé, exécuté par le courtier, inscrit au journal
  const DIT = { demarrer: "Démarrer", arreter: "Arrêter", redemarrer: "Redémarrer", recharger: "Recharger", activer: "Lancer au démarrage", desactiver: "Ne plus lancer au démarrage", pause: "Mettre en pause", reprendre: "Reprendre",
    terminer: "Terminer", forcer: "Forcer l’arrêt", calmer: "Baisser sa priorité" };
  const POURQUOI = {
    service: { demarrer: "Le service démarre.", arreter: "Ce qu’il rend s’arrête. Il ne repartira pas tout seul avant le prochain démarrage de la machine.", redemarrer: "Coupure de quelques secondes, puis il repart.",
      recharger: "Il relit sa configuration, sans coupure.", activer: "Il se lancera à chaque démarrage de la machine.", desactiver: "Il continue de tourner maintenant, mais ne repartira pas au prochain démarrage." },
    conteneur: { demarrer: "Le conteneur repart avec les mêmes réglages.", arreter: "Le service qu’il rend s’arrête. Il ne repartira pas tout seul, même au démarrage de la machine, tant qu’on ne le relance pas.",
      redemarrer: "Coupure de quelques secondes. Les réglages et les volumes sont gardés.", pause: "Ses processus sont gelés : il garde sa mémoire mais ne répond plus.", reprendre: "Ses processus repartent là où ils s’étaient arrêtés." },
    processus: { terminer: "On lui demande de s’arrêter proprement. Il n’y a pas de retour : un processus arrêté ne se relance pas d’ici.", forcer: "Arrêt immédiat, sans lui laisser le temps d’enregistrer. Il n’y a pas de retour.",
      calmer: "Il passe après les autres quand le processeur manque. Le geste se défait." },
  };
  const SANS_RETOUR = { "service.redemarrer": 1, "service.recharger": 1, "conteneur.redemarrer": 1, "processus.terminer": 1, "processus.forcer": 1 };
  const RECHARGEABLES = ["nginx", "apache2", "ssh", "dovecot", "exim4", "postfix", "fail2ban"];
  const bg = (genre, action, cible, libelle, cls) => '<button class="btn s ' + (cls || "") + '" data-a="geste" data-c="' + genre + '" data-x="' + action + '" data-n="' + esc(cible) + '">' + esc(libelle || DIT[action]) + "</button>";
  const jl = (genre, cible) => '<button class="btn s" data-a="journalDe" data-c="' + genre + '" data-n="' + esc(cible) + '">Journal</button>';
  function gestesService(s) {
    if (s.geste === "noyau" || s.geste === "collecteur") return '<button class="btn s ' + (s.geste === "noyau" ? "d" : "") + '" data-a="svc" data-g="' + s.geste + '">' + (s.geste === "noyau" ? "Relancer" : "Redémarrer") + "</button>" + jl("service", s.unite);
    if (s.unite === "cassandra-courtier") return jl("service", s.unite);
    const arret = s.protege ? '<button class="btn s" disabled title="' + esc(s.protege) + '">Arrêter</button>' : bg("service", "arreter", s.unite, "", "d");
    const recharge = RECHARGEABLES.indexOf(s.unite) >= 0 || /^php[\d.]*-fpm$/.test(s.unite) ? bg("service", "recharger", s.unite) : "";
    return (s.etat === "echec" ? bg("service", "redemarrer", s.unite) + arret : s.etat === "actif" ? bg("service", "redemarrer", s.unite) + recharge + arret + '<button class="btn s" data-a="limiter" data-n="' + esc(s.unite) + '">Limiter sa mémoire…</button>' :
      s.etat === "repos" ? bg("service", "demarrer", s.unite, "Lancer maintenant") : bg("service", "demarrer", s.unite, "", "p")) + jl("service", s.unite);
  }
  const boutonDemarrage = (s) => (s.geste === "noyau" || s.geste === "collecteur" || s.unite === "cassandra-courtier" || (s.protege && s.au_demarrage) ? "" :
    ' <button class="btn s" style="margin-left:6px" data-a="geste" data-c="service" data-x="' + (s.au_demarrage ? "desactiver" : "activer") + '" data-n="' + esc(s.unite) + '">' + (s.au_demarrage ? "Ne plus le lancer" : "Le lancer") + "</button>");
  const gestesConteneur = (c) => (c.pause ? bg("conteneur", "reprendre", c.nom, "", "p") + bg("conteneur", "arreter", c.nom, "", "d") : c.tourne ? bg("conteneur", "redemarrer", c.nom) + bg("conteneur", "pause", c.nom) + bg("conteneur", "arreter", c.nom, "", "d") :
    bg("conteneur", "demarrer", c.nom, "", "p")) + jl("conteneur", c.nom);
  const gestesProcessus = (p) => (p.pid == null || p.protege ? "" : bg("processus", "terminer", p.pid) + bg("processus", "forcer", p.pid, "", "d") + bg("processus", "calmer", p.pid));
  function blocGestes() {
    const g = S.gestes; if (!g) return "";
    return sec("Derniers gestes", "faits depuis cette page · le plus récent d’abord · heure du serveur", g.length ? '<div class="rows">' + g.slice(0, 8).map((x) => '<div class="row"><div class="nm"><b style="white-space:normal">' + esc(x.detail.charAt(0).toUpperCase() + x.detail.slice(1)) +
      (x.cible ? ' <span class="mono">' + esc(x.cible) + "</span>" : "") + "</b><small>" + jour(x.ts) + " · " + esc(x.qui || "?") + '</small></div><div class="mil" style="white-space:normal">' + esc(x.resultat) + '</div><div class="cote">' +
      (x.defaisable ? '<button class="btn s" data-a="annuler" data-i="' + x.id + '">Annuler</button>' : "<small>sans retour</small>") + "</div></div>").join("") + "</div>" : '<p class="vide">Aucun geste fait depuis cette page.</p>');
  }
  // Ce qu'un geste vient de changer, tenu jusqu'au relevé suivant du collecteur (il ne relit les conteneurs que toutes les cinq minutes, les services toutes les trente
  // secondes) : sans cela la page montrerait l'état d'avant, et un conteneur en pause n'offrirait pas « Reprendre ».
  const FRAIS = { conteneur: {}, service: {} };
  const INVERSE_DIT = { "mettre en pause": "reprendre", reprendre: "pause", "arrêter": "demarrer", "démarrer": "arreter", "lancer au démarrage": "desactiver", "ne plus lancer au démarrage": "activer" };
  function noterFrais(genre, cible, action, res) { if (!FRAIS[genre]) return; FRAIS[genre][cible] = { action: action, apres: res && res.apres, fin: Date.now() + (genre === "conteneur" ? 330000 : 45000) }; appliquerFrais(); }
  function appliquerFrais() {
    const d = S.d, maintenant = Date.now(); if (!d) return;
    (d.conteneurs || []).forEach((c) => { const f = FRAIS.conteneur[c.nom]; if (!f) return; if (f.fin < maintenant) { delete FRAIS.conteneur[c.nom]; return; }
      const e = f.apres || { arreter: "exited", pause: "paused" }[f.action] || "running";
      c.pause = e === "paused"; c.tourne = e === "running" || e === "paused"; c.etat = e === "paused" ? "en pause" : e === "running" ? (f.action === "reprendre" ? "reparti à l’instant" : "relancé à l’instant") : "arrêté à l’instant"; });
    ((d.services || {}).suivis || []).forEach((s) => { const f = FRAIS.service[s.unite]; if (!f) return; if (f.fin < maintenant) { delete FRAIS.service[s.unite]; return; }
      if (f.action === "arreter") { s.etat = "arret"; s.sous_etat = "arrêté à l’instant"; s.pid = null; s.memoire_mo = null; } else if (f.action === "demarrer" || f.action === "redemarrer") { s.etat = "actif"; s.sous_etat = "relancé à l’instant"; }
      else if (f.action === "activer") s.au_demarrage = true; else if (f.action === "desactiver") s.au_demarrage = false; });
  }
  async function chargerGestes() { try { const r = await agir("securite.machine_gestes", { limite: 12 }); S.gestes = (r && r.gestes) || []; } catch (e) { S.gestes = null; } }
  async function chargerRd() { try { S.rd = await agir("securite.redemarrage_etat"); } catch (e) { S.rd = null; } if (S.page === "fiche") rendre(); return S.rd; }
  const apresGeste = async (texte) => { dire(texte, "ok"); await chargerGestes(); rendre(); setTimeout(charger, 2500); };
  // Une feuille qui demande une valeur : `lire(m)` rend la valeur, ou rien pour garder la feuille ouverte (la saisie n'est pas bonne).
  function saisie(titre, html, oui, danger, lire) {
    return new Promise((fin) => {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
      const m = document.createElement("div"); m.className = "kit-m mc"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titre); m.style.width = "min(640px,calc(100% - 32px))";
      m.innerHTML = "<h2>" + esc(titre) + "</h2>" + html + '<p class="note" data-r style="color:var(--danger);min-height:1.2em;margin:6px 0 0"></p><div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn ' + (danger ? "dng" : "pri") + '" data-c="oui">' + esc(oui) + "</button></div>";
      const clore = (r) => { v.remove(); m.remove(); fin(r); };
      v.addEventListener("click", () => clore(null));
      m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (!b || b.disabled) return; if (b.dataset.c !== "oui") return clore(null); const r = lire(m); if (r && r.erreur) { m.querySelector("[data-r]").textContent = r.erreur; return; } if (r) clore(r); });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(null); });
      document.body.appendChild(v); document.body.appendChild(m); const f = m.querySelector("input,[data-c=non]"); if (f) f.focus();
    });
  }
  const utc = (t) => new Date(t).toISOString().slice(0, 19).replace("T", " ");
  const G = {
    geste: async (b) => {
      const genre = b.dataset.c, action = b.dataset.x, cible = b.dataset.n, d = D();
      let args, plus = "", nom = cible;
      if (genre === "service") { const s = ((d.services || {}).suivis || []).find((x) => x.unite === cible) || {}; args = { service: cible, action: action }; if (action === "arreter" && s.si_arret) plus = "<p><b>" + esc(s.si_arret) + "</b></p>"; if (action !== "arreter" && /^(nginx|apache2|ssh)$/.test(cible) && /redemarrer|recharger/.test(action)) plus = "<p>Sa configuration est testée d’abord : si elle est fausse, rien n’est touché.</p>"; }
      else if (genre === "conteneur") { const c = (d.conteneurs || []).find((x) => x.nom === cible) || {}; args = { nom: cible, action: action }; if (action === "arreter" && (c.proxys || []).length) plus = "<p><b>" + esc(c.proxys[0].nom) + " ne répondra plus.</b></p>"; }
      else { const p = (d.processus || []).find((x) => String(x.pid) === String(cible)); if (!p) return dire("Ce processus n’est plus dans la liste : relève la page.", "err"); args = { pid: p.pid, action: action, commande: p.commande }; nom = court(p.commande) + " (n° " + p.pid + ")"; }
      const retour = SANS_RETOUR[genre + "." + action] ? "" : "<p>Le geste s’inscrit au journal et peut s’annuler depuis « Derniers gestes ».</p>";
      const titre = { activer: "Lancer " + nom + " au démarrage ?", desactiver: "Ne plus lancer " + nom + " au démarrage ?", forcer: "Forcer l’arrêt de " + nom + " ?", calmer: "Baisser la priorité de " + nom + " ?", pause: "Mettre " + nom + " en pause ?" }[action] || DIT[action] + " " + nom + " ?";
      if (!await K.confirmer(titre, plus + "<p>" + POURQUOI[genre][action] + "</p>" + retour, DIT[action], action === "arreter" || action === "forcer" || action === "terminer")) return;
      dire(titre.replace(/ \?$/, "") + "…");
      const res = await agir("securite." + genre + "_geste", args);
      if (genre === "processus" && action !== "calmer") S.pr = ""; else noterFrais(genre, cible, action, res);
      return apresGeste(nom + " : fait, vérifié par le courtier.");
    },
    journalDe: async (b) => { const service = b.dataset.c === "service", r = await agir(service ? "securite.service_journal" : "securite.conteneur_journal", service ? { service: b.dataset.n } : { nom: b.dataset.n });
      feuille("Journal de " + b.dataset.n, '<p class="note">Les 200 dernières lignes, en lecture seule.</p><pre style="margin:0;max-height:52vh;overflow:auto;font:11.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word">' + esc((r && r.texte) || "Le journal est vide.") + "</pre>"); },
    limiter: async (b) => {
      const s = ((D().services || {}).suivis || []).find((x) => x.unite === b.dataset.n) || {}, total = (D().memoire || {}).total_mo;
      const r = await saisie("Limiter la mémoire de " + b.dataset.n, "<p>Au-delà de cette limite, le noyau Linux tue le service plutôt que de laisser la machine manquer de mémoire ; systemd le relance s’il est réglé pour.</p>" +
        (s.memoire_mo != null ? "<p>Il occupe " + mo(s.memoire_mo) + " en ce moment" + (total ? ", sur " + mo(total) + " dans la machine" : "") + ".</p>" : "") +
        '<label style="display:flex;align-items:center;gap:8px">Limite <input type="number" min="128" step="64" value="' + Math.max(256, Math.ceil((s.memoire_mo || 256) * 2 / 64) * 64) + '" data-v style="width:120px"> Mo</label>', "Poser la limite", false,
        (m) => { const v = parseInt(m.querySelector("[data-v]").value, 10); return v >= 128 && (!total || v <= total) ? { mo: v } : { erreur: "Entre 128 Mo et la mémoire de la machine." }; });
      if (!r) return;
      await agir("securite.service_memoire", { service: b.dataset.n, mo: r.mo });
      return apresGeste("La mémoire de " + b.dataset.n + " est limitée à " + mo(r.mo) + ".");
    },
    bannir: async (b) => { const s = b.dataset.ip ? { adresse: b.dataset.ip } : (D().sessions || [])[+b.dataset.i]; if (!s) return;
      if (!await K.confirmer("Bannir l’adresse " + s.adresse + " ?", "<p>fail2ban refuse toute nouvelle connexion SSH depuis cette adresse. Le geste s’annule depuis « Derniers gestes » ; la liste des bannies est dans Sécurité › Défenses.</p>" +
        "<p>Le courtier refuse une adresse privée, de ton réseau privé, ou qui s’est connectée avec succès depuis trente jours.</p>", "Bannir", true)) return;
      await agir("securite.adresse_bannir", { ip: s.adresse }); return apresGeste("L’adresse " + s.adresse + " est bannie."); },
    dehors: async () => { if (!await K.confirmer("Tout le monde dehors ?", "<p>Toutes les sessions qui tiennent un terminal sur la machine sont fermées, la tienne comprise si tu y es connecté. Il n’y a pas de retour : une session fermée se rouvre en se reconnectant.</p>", "Fermer toutes les sessions", true)) return;
      const r = await agir("securite.sessions_fermer_toutes", {}); return apresGeste(((r && r.fermees) || []).length + " session(s) fermée(s)."); },
    annuler: async (b) => { const g = (S.gestes || []).find((x) => String(x.id) === b.dataset.i); if (!g) return;
      if (!await K.confirmer("Annuler ce geste ?", "<p>" + esc(g.detail) + (g.cible ? " · " + esc(g.cible) : "") + "</p><p>Le courtier rejoue le retour que le geste avait rendu, une seule fois.</p>", "Annuler le geste")) return;
      await agir("securite.machine_geste_defaire", { id: g.id }); if (g.geste === "redemarrer") await chargerRd();
      if (INVERSE_DIT[g.detail]) noterFrais(g.geste, g.cible, INVERSE_DIT[g.detail], null);
      return apresGeste("Le geste est annulé."); },
    retourLu: async () => { await agir("securite.redemarrage_lu", {}); if (S.rd) S.rd.retour = null; rendre(); },
    annulerRedemarrage: async () => { await chargerGestes(); const g = (S.gestes || []).find((x) => x.geste === "redemarrer" && x.defaisable); if (!g) return dire("Ce redémarrage n’a pas été prévu depuis cette page : il s’annule sur la machine (shutdown -c).", "err");
      if (!await K.confirmer("Annuler le redémarrage prévu ?", "<p>La machine ne redémarrera pas.</p>", "Annuler le redémarrage")) return;
      await agir("securite.machine_geste_defaire", { id: g.id }); await chargerRd(); return apresGeste("Le redémarrage est annulé."); },
    redemarrer: async () => {
      dire("Vérifications avant de redémarrer…");
      const e = await chargerRd(), nom = (D().machine || {}).nom || (e && e.machine) || "";
      if (!e) return dire("Les vérifications n’ont pas répondu : la machine ne se redémarre pas sans elles.", "err");
      if (e.prevu) return dire("Un redémarrage est déjà prévu le " + e.prevu + " : annule-le d’abord.", "err");
      const liste = (t, l, c) => (l.length ? '<p style="margin:6px 0 2px' + (c ? ";color:var(--" + c + ")" : "") + '"><b>' + t + "</b></p><ul style=\"margin:0 0 6px 18px\">" + l.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>" : "");
      const nr = e.ne_reviendront_pas || {}, bloque = (e.obstacles || []).length > 0;
      const r = await saisie("Redémarrer la machine " + nom, "<p>Tout s’arrête une à deux minutes : les sites, les conteneurs, le réseau privé, et Cassandra elle-même. Tu seras déconnecté de cette page.</p>" +
        liste("La machine ne part pas maintenant :", e.obstacles || [], "danger") + liste("Sessions ouvertes, qui seront coupées :", (e.sessions || []).map((s) => s[0] + " · " + s[1] + (s[2] ? " · " + s[2] : ""))) +
        liste("Ne reviendront pas seuls :", (nr.services || []).map((s) => "service " + s + " (pas lancé au démarrage)").concat((nr.conteneurs || []).map((c) => "conteneur " + c + " (sans politique de redémarrage)")), "warn") +
        ((nr.services || []).length + (nr.conteneurs || []).length ? "" : "<p>Tout ce qui tourne est réglé pour revenir seul.</p>") +
        '<p style="margin:10px 0 4px"><b>Quand</b> <small>il est ' + esc(e.heure || "?") + ' sur le serveur</small></p><label style="display:block"><input type="radio" name="mc-q" value="maintenant" checked> dans une minute</label>' +
        '<label style="display:block"><input type="radio" name="mc-q" value="heure"> à <input type="time" data-h value="03:00" style="width:110px"> <small>heure du serveur</small></label>' +
        '<label style="display:block;margin-top:8px"><input type="checkbox" data-f checked> poser une fenêtre de maintenance de 20 minutes dans le Sensorium, pour que les alertes se taisent</label>' +
        '<p style="margin:10px 0 4px"><b>Pour confirmer, tape le nom de la machine</b></p><input type="text" data-n autocomplete="off" placeholder="' + esc(nom) + '" style="width:220px"' + (bloque ? " disabled" : "") + ">", "Redémarrer la machine", true,
        (m) => { if (bloque) return { erreur: "La machine ne part pas tant que ce qui est en cours n’est pas fini." }; const q = m.querySelector('input[name="mc-q"]:checked').value, h = m.querySelector("[data-h]").value;
          if (m.querySelector("[data-n]").value.trim() !== nom) return { erreur: "Ce n’est pas le nom de la machine." }; if (q === "heure" && !/^\d\d:\d\d$/.test(h)) return { erreur: "Heure illisible." };
          return { quand: q === "heure" ? h : "maintenant", fenetre: m.querySelector("[data-f]").checked }; });
      if (!r) return;
      const res = await agir("securite.machine_redemarrer", { quand: r.quand, nom: nom });
      if (r.fenetre) {
        let dans = 60000;
        if (r.quand !== "maintenant" && /^\d\d:\d\d$/.test(e.heure || "")) { const mn = (t) => +t.slice(0, 2) * 60 + +t.slice(3, 5); dans = ((mn(r.quand) - mn(e.heure) + 1440) % 1440) * 60000; }
        try { await agir("sensorium.fenetre_poser", { portee: "*", debut: utc(Date.now() + dans - 60000), fin: utc(Date.now() + dans + 1200000), motif: "redémarrage de la machine " + nom }); } catch (x) { dire("Le redémarrage est prévu, mais la fenêtre de maintenance n’a pas pu être posée : " + msg(x), "err"); }
      }
      await chargerRd(); return apresGeste("Le redémarrage est prévu le " + ((res && res.prevu) || "?") + " (heure du serveur). Il s’annule jusqu’au départ.");
    },
  };
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
    tri: () => { S.tri = S.tri === "cpu" ? "mem" : "cpu"; rendre(); },
    aller: (b) => { S[b.dataset.k] = b.dataset.n; if (b.dataset.k === "sv") { S.svF = "tous"; S.svQ = ""; } page(b.dataset.p); },
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
  Object.assign(A, G);
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
    rendre(); charger(); if (S.page === "fiche") chargerRd(); if (R) R.scrollTop = 0;
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
