// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La page des modules : cartes, détail, changements mis en attente avec leur impact
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f004ac
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La page « Modules et applications » : une carte par module (état, importance déclarée, interrupteur, accès aux réglages), un tiroir de détail (ce qui s'arrête sans lui, dépendances, ce qu'il peut faire hors de lui) et les changements d'activation mis en attente, avec leur impact dit avant d'être appliqués.
// MÉTHODE    : le catalogue de modules-ui.js (modules.lister) fournit tout ; l'impact d'un jeu de changements se calcule sur le graphe requiert / requis_par ; rien n'est appliqué avant l'accord : les désactivations d'abord (les dépendants avant leurs dépendances), puis les activations (modules.activer tire ses dépendances) ; tout texte dynamique est échappé
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f004ac ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };
  const MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace";

  const ICONES = {
    socle: '<path d="M12 3l8 4v5c0 4.4-3.1 7.6-8 9-4.9-1.4-8-4.6-8-9V7z"/>',
    securite: '<rect x="5" y="10" width="14" height="10" rx="2.5"/><path d="M8 10V7a4 4 0 018 0v3"/>',
    reseau: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3 3.2 15 0 18M12 3c-3.2 3-3.2 15 0 18"/>',
    communication: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 7l9 6 9-6"/>',
    echanges: '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
    canaux: '<path d="M4 5h16v11H9l-5 4z"/>',
    agents: '<rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01"/>',
    gestion: '<rect x="3.5" y="4" width="17" height="16" rx="2.5"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    supervision: '<path d="M3 12s3.5-7 9-7 9 7 9 7-3.5 7-9 7-9-7-9-7z"/><circle cx="12" cy="12" r="3"/>',
    hebergement: '<rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01"/>',
    systeme: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    evolution: '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>',
    autres: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>'
  };
  const ICO_GEAR = '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>';
  const CRIT = { vital: ["Vital", "vi", "La maison ne tient pas sans lui."], important: ["Important", "al", "Une fonction de la maison s'arrête sans lui."], optionnel: ["Optionnel", "nu", "On peut s'en passer sans rien casser."] };

  const CSS = ".mp{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.mp *{box-sizing:border-box}.mp h1,.mp h2,.mp h3,.mp p{margin:0}" +
    ".mp .note{font-size:12.5px;color:var(--txt-soft)}.mp .mono{font-family:" + MONO + "}" +
    ".mp .bandeau{font-size:12.5px;color:var(--txt-soft);background:var(--surface);border:1px solid var(--accent);border-radius:12px;padding:9px 13px}.mp .bandeau.al{border-color:var(--warn);color:var(--warn)}" +
    ".mp .btn,.mpo .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 14px;font:600 13px 'Inter',system-ui,sans-serif;cursor:pointer;white-space:nowrap}" +
    ".mp .btn:hover:not([disabled]),.mpo .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.mp .btn.pri,.mpo .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.mp .btn.pri:hover:not([disabled]),.mpo .btn.pri:hover:not([disabled]){color:var(--on-accent,#fff);filter:brightness(1.08)}" +
    ".mp .btn.dng,.mpo .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}.mp .btn[disabled],.mpo .btn[disabled]{opacity:.45;cursor:not-allowed}" +
    ".mp .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}.mp .stat{text-align:left;background:var(--surface);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:14px;padding:11px 14px;cursor:pointer;font:inherit;color:inherit;display:flex;flex-direction:column;gap:1px;box-shadow:var(--shadow-glass)}" +
    ".mp .stat b{font:650 24px/1.1 " + MONO + ";color:var(--txt-strong,var(--txt))}.mp .stat span{font-size:12.5px;color:var(--txt-soft)}.mp .stat.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}.mp .stat.al b{color:var(--warn)}.mp .stat.ok b{color:var(--ok)}" +
    ".mp .barre{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.mp .barre input{flex:1 1 240px;min-width:0;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);color:var(--txt);border-radius:10px;padding:8px 12px;font:14px 'Inter',system-ui,sans-serif}" +
    ".mp .barre input:focus{outline:2px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:1px}.mp .fams{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12.5px;color:var(--txt-soft)}" +
    ".mp .fam{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;font:600 12.5px 'Inter',system-ui,sans-serif;color:var(--txt-soft);cursor:pointer}.mp .fam.on{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}" +
    ".mp .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}" +
    ".mp .carte{background:var(--surface);backdrop-filter:blur(14px) saturate(150%);border:1px solid var(--line);border-radius:16px;padding:14px 15px;display:flex;flex-direction:column;gap:9px;box-shadow:var(--shadow-glass);cursor:pointer;text-align:left;font:inherit;color:inherit}" +
    ".mp .carte:hover{border-color:var(--accent)}.mp .carte.att{border-color:var(--warn);box-shadow:0 0 0 1px var(--warn) inset}.mp .carte .l1{display:flex;gap:10px;align-items:center}" +
    ".mp .ico,.mpo .ico{flex:none;width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent)}.mp .ico svg,.mpo .ico svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}" +
    ".mp .carte.off .ico{background:var(--line);color:var(--txt-faint)}.mp .carte h3{font:650 15px/1.25 'Inter',system-ui,sans-serif;color:var(--txt-strong,var(--txt))}.mp .carte .id{font:11.5px " + MONO + ";color:var(--txt-faint)}" +
    ".mp .carte .desc{font-size:12.5px;color:var(--txt-soft);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.9em}.mp .carte .pied{display:flex;gap:6px 8px;flex-wrap:wrap;align-items:center;margin-top:auto}" +
    ".mp .p,.mpo .p{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:2px 9px;font:600 11px 'Inter',system-ui,sans-serif;background:var(--surface-solid,var(--surface));color:var(--txt-soft);border:1px solid var(--line);white-space:nowrap}.mp .p::before,.mpo .p::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}.mp .p.nu::before,.mpo .p.nu::before{display:none}" +
    ".mp .p.ok,.mpo .p.ok{color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:color-mix(in srgb,var(--ok) 28%,transparent)}.mp .p.al,.mpo .p.al{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}" +
    ".mp .p.dg,.mpo .p.dg{color:var(--danger);background:color-mix(in srgb,var(--danger) 12%,transparent);border-color:color-mix(in srgb,var(--danger) 28%,transparent)}.mp .p.vi,.mpo .p.vi{background:var(--txt-strong,#111);color:var(--bg,#fff);border-color:transparent}.mp .p.vi::before,.mpo .p.vi::before{background:var(--danger)}" +
    ".mp .rgl,.mpo .rgl{flex:none;width:32px;height:32px;border-radius:9px;border:1px solid var(--line);background:var(--surface-solid,var(--surface));color:var(--txt-soft);display:grid;place-items:center;cursor:pointer;padding:0;margin-left:auto}.mp .rgl svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}" +
    ".mp .rgl:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.mp .rgl[disabled]{opacity:.4;cursor:not-allowed}" +
    ".mp .inter{position:relative;display:inline-block;width:42px;height:24px;flex:none}.mp .inter input{opacity:0;position:absolute;inset:0;width:100%;height:100%;margin:0;cursor:pointer;z-index:1}.mp .inter i{position:absolute;inset:0;background:var(--line-strong,#bbb);border-radius:99px;transition:.15s}" +
    ".mp .inter i::after{content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;transition:.15s;box-shadow:0 1px 3px rgba(0,0,0,.3)}.mp .inter input:checked+i{background:var(--accent)}.mp .inter input:checked+i::after{left:21px}.mp .inter input:disabled{cursor:not-allowed}.mp .inter input:disabled+i{opacity:.45}.mp .inter.att i{outline:2px solid var(--warn);outline-offset:1px}" +
    ".mp .vide{padding:40px 10px;text-align:center;color:var(--txt-soft);grid-column:1/-1}" +
    // les surcouches (tiroir, plateau, feuille) vivent dans le body : le verre dépoli du conteneur ne les déplace pas
    ".mpo .voile{position:fixed;inset:0;background:rgba(5,20,18,.45);backdrop-filter:blur(2px);opacity:0;pointer-events:none;transition:.18s;z-index:2000}.mpo .voile.o{opacity:1;pointer-events:auto}" +
    ".mpo .tiroir{position:fixed;top:0;right:0;bottom:0;width:min(460px,100%);background:var(--bg);color:var(--txt);border-left:1px solid var(--line-strong,var(--line));transform:translateX(100%);transition:.22s;z-index:2001;display:flex;flex-direction:column;box-shadow:-20px 0 50px -20px rgba(0,0,0,.4);font:13.5px/1.5 'Inter',system-ui,sans-serif}.mpo .tiroir.o{transform:none}" +
    ".mpo .th{padding:18px 20px 12px;display:flex;flex-direction:column;gap:8px;border-bottom:1px solid var(--line)}.mpo .th .l1{display:flex;gap:12px;align-items:center}.mpo .th h2{margin:0;font:650 19px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.mpo .x{margin-left:auto;border:0;background:var(--line);color:var(--txt);width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:16px;flex:none}" +
    ".mpo .tc{flex:1;overflow:auto;padding:16px 20px 24px;display:flex;flex-direction:column;gap:18px}.mpo .tc p{margin:0}.mpo .lib{font:600 10.5px 'Inter',sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint);margin-bottom:6px}.mpo .note{font-size:12.5px;color:var(--txt-soft)}.mpo .mono{font-family:" + MONO + "}" +
    ".mpo .sans{border:1px solid var(--line);border-radius:12px;padding:11px 13px;background:var(--surface);display:flex;flex-direction:column;gap:6px}.mpo .sans.vital{border-color:color-mix(in srgb,var(--danger) 40%,transparent)}" +
    ".mpo .cles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.mpo .cle{border:1px solid var(--line);border-radius:12px;padding:9px 11px;background:var(--surface)}.mpo .cle b{display:block;font:650 20px " + MONO + ";color:var(--txt-strong,var(--txt))}.mpo .cle span{font-size:11.5px;color:var(--txt-soft)}" +
    ".mpo .dep{display:flex;flex-direction:column;gap:6px}.mpo .dep .rang{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12.5px;color:var(--txt-soft)}.mpo .dep .fleche{text-align:center;color:var(--txt-faint);line-height:1}.mpo .dep .centre{border:1.5px solid var(--accent);border-radius:12px;padding:8px 12px;text-align:center;font-weight:650;color:var(--txt-strong,var(--txt));background:color-mix(in srgb,var(--accent) 8%,transparent)}" +
    ".mpo .chip{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,#fff);border-radius:10px;padding:4px 10px;font:600 12px 'Inter',sans-serif;color:var(--txt);cursor:pointer;display:inline-flex;gap:6px;align-items:center}.mpo .chip i{width:7px;height:7px;border-radius:50%;background:var(--ok)}.mpo .chip.off i{background:var(--txt-faint)}" +
    ".mpo .perms{display:flex;flex-direction:column;gap:6px}.mpo .perms div{display:flex;gap:9px;align-items:flex-start}.mpo .tp{border-top:1px solid var(--line);padding:14px 20px;display:flex;gap:8px;flex-wrap:wrap;background:var(--bg)}.mpo .tp .sp{flex:1}" +
    ".mpo .plateau{position:fixed;left:50%;bottom:16px;transform:translate(-50%,170%);transition:.25s;z-index:1990;width:min(720px,calc(100% - 32px));background:var(--surface-solid,var(--bg));color:var(--txt);border:1px solid var(--warn);border-radius:16px;box-shadow:0 18px 50px -14px rgba(0,0,0,.45);padding:12px 14px;display:flex;gap:10px 14px;flex-wrap:wrap;align-items:center;font:13.5px/1.5 'Inter',system-ui,sans-serif}" +
    ".mpo .plateau.o{transform:translate(-50%,0)}.mpo .plateau .t{flex:1 1 220px;min-width:0}.mpo .plateau b{color:var(--txt-strong,var(--txt))}" +
    ".mpo .feuille{position:fixed;left:50%;top:50%;transform:translate(-50%,-46%) scale(.98);opacity:0;pointer-events:none;transition:.18s;z-index:2002;width:min(560px,calc(100% - 28px));max-height:calc(100% - 40px);overflow:auto;background:var(--bg);color:var(--txt);border:1px solid var(--line-strong,var(--line));border-radius:18px;box-shadow:0 30px 80px -20px rgba(0,0,0,.55);padding:20px;display:flex;flex-direction:column;gap:14px;font:13.5px/1.5 'Inter',system-ui,sans-serif}" +
    ".mpo .feuille.o{opacity:1;pointer-events:auto;transform:translate(-50%,-50%)}.mpo .feuille h2{margin:0;font:650 19px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.mpo .ligne{display:flex;gap:10px;align-items:flex-start;padding:9px 0;border-top:1px solid var(--line)}.mpo .ligne:first-of-type{border-top:0}" +
    ".mpo .signe{flex:none;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font:700 14px 'Inter',sans-serif;color:#fff}.mpo .signe.plus{background:var(--ok)}.mpo .signe.moins{background:var(--danger)}" +
    ".mpo .bandeau{font-size:12.5px;border:1px solid var(--danger);color:var(--danger);border-radius:12px;padding:9px 13px}.mpo .bandeau.al{border-color:var(--warn);color:var(--warn)}" +
    "@media (max-width:640px){.mp .grille{grid-template-columns:minmax(0,1fr)}.mpo .tiroir{width:100%}}";

  // ── la page ────────────────────────────────────────────────────────────────
  CASS.pageModules = function (el, fam, ctx) {
    const anc = document.getElementById("mp-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "mp-css"; st.textContent = CSS; document.head.appendChild(st);
    document.querySelectorAll(".mpo").forEach((x) => x.remove());                              // une seule série de surcouches à la fois
    const U = CASS.modulesUi, cat = () => U.catalogue(), par = (id) => cat().find((m) => m.id === id);
    const gere = () => U.gere();
    const S = { filtre: "tous", niv: "tous", q: "", sel: null, att: new Map(), occupe: false };
    const voulu = (id) => (S.att.has(id) ? S.att.get(id) : (par(id) || {}).etat === "actif");
    const nom = (id) => (par(id) || { nom: id }).nom;
    const actifsApres = (id) => cat().filter((x) => (x.requiert || []).indexOf(id) >= 0 && x.etat === "actif").map((x) => x.id);

    // l'impact d'un jeu de changements : ce qui sera activé (demandé ou tiré par une dépendance), désactivé, et ce qui bloque
    function impact() {
      const act = new Set(), des = new Set(), bloc = [];
      const tirer = (id) => (par(id).requiert || []).forEach((r) => { if (par(r) && !voulu(r) && !act.has(r)) { act.add(r); tirer(r); } });
      S.att.forEach((v, id) => { if (v) { act.add(id); tirer(id); } else des.add(id); });
      des.forEach((id) => (par(id).requis_par || []).forEach((r) => { if (par(r) && voulu(r) && !des.has(r)) bloc.push([id, r]); }));
      return { act: [...act].filter((id) => par(id).etat !== "actif"), des: [...des], bloc };
    }
    const crit = (m) => (CRIT[m.importance] ? m.importance : "");
    const ico = (f) => '<span class="ico"><svg viewBox="0 0 24 24">' + (ICONES[f] || ICONES.autres) + "</svg></span>";
    const verrou = (m) => !gere() || m.essentiel || m.etat === "a_installer" || m.etat === "refuse" || (m.etat === "actif" ? !(m.peut_desactiver || {}).ok && !(m.requis_par || []).length : !(m.peut_activer || {}).ok);
    const raisonVerrou = (m) => (!gere() ? "Instance de développement : tout est chargé" : m.essentiel ? "Module essentiel : toujours actif" : m.etat === "a_installer" ? "À installer d'abord sur la machine" : m.etat === "refuse" ? "Extension écartée" : m.etat === "actif" ? "" : ((m.peut_activer || {}).raison || ""));

    function carte(m) {
      const on = voulu(m.id), att = S.att.has(m.id), c = crit(m), lock = verrou(m);
      const bloque = lock && !(m.etat === "actif" && !m.essentiel && gere() && (m.requis_par || []).length);       // un module utilisé par d'autres reste basculable : l'impact le dira
      const pE = m.etat === "actif" ? '<span class="p ok">Actif</span>' : m.etat === "a_installer" ? '<span class="p al">À installer</span>' : m.etat === "refuse" ? '<span class="p dg">Refusé</span>' : '<span class="p nu">Inactif</span>';
      return '<div class="carte' + (m.etat === "actif" ? "" : " off") + (att ? " att" : "") + '" data-id="' + esc(m.id) + '" role="button" tabindex="0"><div class="l1">' + ico(m.famille) + '<div style="min-width:0"><h3>' + esc(m.nom) + '</h3><div class="id">' + esc(m.id) + (m.version ? " · v" + esc(m.version) : "") + "</div></div>" +
        '<button class="rgl" data-reg="' + esc(m.id) + '"' + (m.etat === "actif" ? "" : " disabled") + ' title="' + (m.etat === "actif" ? "Réglages de " + esc(m.nom) : "Activez le module pour accéder à ses réglages") + '" aria-label="Réglages de ' + esc(m.nom) + '"><svg viewBox="0 0 24 24">' + ICO_GEAR + "</svg></button>" +
        '<label class="inter' + (att ? " att" : "") + '" title="' + esc(bloque ? raisonVerrou(m) : on ? "Désactiver" : "Activer") + '"><input type="checkbox" data-bas="' + esc(m.id) + '"' + (on ? " checked" : "") + (bloque ? " disabled" : "") + ' aria-label="Activer ' + esc(m.nom) + '"><i></i></label></div>' +
        '<div class="desc">' + esc(m.description || "") + '</div><div class="pied">' + pE + (c ? '<span class="p ' + CRIT[c][1] + '" title="' + esc(CRIT[c][2]) + '">' + CRIT[c][0] + "</span>" : "") + (m.confiance && m.confiance !== "interne" ? '<span class="p nu">' + esc(m.confiance) + "</span>" : "") +
        (att ? '<span class="p al">' + (S.att.get(m.id) ? "sera activé" : "sera désactivé") + "</span>" : "") + '<span class="note" style="margin-left:auto">' + (m.capacites != null ? m.capacites + " capacités" : "") + "</span></div></div>";
    }
    const visibles = () => cat().filter((m) => {
      if (fam && fam !== "tous" && (m.famille || "autres") !== fam) return false;
      if (S.filtre === "actif" && m.etat !== "actif") return false;
      if (S.filtre === "inactif" && m.etat !== "inactif") return false;
      if (S.filtre === "attention" && !(m.etat === "a_installer" || m.etat === "refuse")) return false;
      if (S.niv !== "tous" && crit(m) !== S.niv) return false;
      if (S.q && !((m.nom || "") + " " + m.id + " " + (m.description || "") + " " + ((m.permissions || {}).reseau || []).join(" ")).toLowerCase().includes(S.q)) return false;
      return true;
    });

    // ── dessin ────────────────────────────────────────────────────────────────
    let sur;                                                                   // les surcouches (tiroir, plateau, feuille, voile)
    function surcouches() {
      sur = document.createElement("div"); sur.className = "mpo";
      sur.innerHTML = '<div class="voile"></div><aside class="tiroir" aria-label="Détail du module"></aside><div class="plateau"></div><div class="feuille" role="dialog" aria-modal="true"></div>';
      document.body.appendChild(sur);
      sur.querySelector(".voile").addEventListener("click", fermerTout);
      sur.addEventListener("click", surClic);
    }
    const Q = (s) => sur.querySelector(s);
    function dessiner() {
      const base = cat().filter((m) => !fam || fam === "tous" || (m.famille || "autres") === fam);
      const n = (k) => base.filter(k).length;
      const stats = [["tous", "Modules", base.length, ""], ["actif", "Actifs", n((m) => m.etat === "actif"), "ok"], ["inactif", "Inactifs", n((m) => m.etat === "inactif"), ""], ["attention", "À regarder", n((m) => m.etat === "a_installer" || m.etat === "refuse"), "al"]];
      const nivs = ["tous", "vital", "important", "optionnel"];
      const v = visibles();
      el.innerHTML = '<div class="mp">' +
        (!gere() ? '<div class="bandeau"><b>Instance de développement.</b> Tous les modules sont chargés : l’activation et la désactivation sont indisponibles ici. Les réglages et la console de chaque module restent accessibles.</div>' : "") +
        '<div class="stats">' + stats.map((s) => '<button type="button" class="stat ' + s[3] + (S.filtre === s[0] ? " on" : "") + '" data-f="' + s[0] + '"><b>' + s[2] + "</b><span>" + s[1] + "</span></button>").join("") + "</div>" +
        '<div class="barre"><input id="mp-q" type="search" placeholder="Chercher un module, une capacité, un fournisseur…" aria-label="Chercher" value="' + esc(S.q) + '"></div>' +
        '<div class="fams"><span>Importance :</span>' + nivs.map((k) => '<button type="button" class="fam' + (S.niv === k ? " on" : "") + '" data-niv="' + k + '">' + (k === "tous" ? "Toutes" : CRIT[k][0] + " (" + base.filter((m) => crit(m) === k).length + ")") + "</button>").join("") + "</div>" +
        '<div class="grille">' + (v.length ? v.map(carte).join("") : '<div class="vide">Aucun module ne correspond.</div>') + "</div></div>";
      lierPage();
      plateau();
      if (S.sel) tiroir(S.sel, true);
    }
    function lierPage() {
      el.querySelectorAll("[data-f]").forEach((b) => b.addEventListener("click", () => { S.filtre = b.dataset.f; dessiner(); }));
      el.querySelectorAll("[data-niv]").forEach((b) => b.addEventListener("click", () => { S.niv = b.dataset.niv; dessiner(); }));
      el.querySelectorAll(".carte").forEach((c) => {
        c.addEventListener("click", (e) => { if (e.target.closest(".inter") || e.target.closest(".rgl")) return; tiroir(c.dataset.id); });
        c.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target === c) tiroir(c.dataset.id); });
      });
      el.querySelectorAll("[data-reg]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); reglages(b.dataset.reg); }));
      el.querySelectorAll("[data-bas]").forEach((b) => b.addEventListener("change", () => bascule(b.dataset.bas, b.checked)));
      const q = el.querySelector("#mp-q"); if (q) q.addEventListener("input", () => { S.q = q.value.trim().toLowerCase(); const pos = q.selectionStart; dessiner(); const n = el.querySelector("#mp-q"); n.focus(); n.setSelectionRange(pos, pos); });
    }
    function reglages(id) { const m = par(id); if (CASS.ouvrirConsole) CASS.ouvrirConsole(id, m ? m.nom : id, "reglages"); }
    function bascule(id, v) { const m = par(id); if ((m.etat === "actif") === v) S.att.delete(id); else S.att.set(id, v); dessiner(); }

    function plateau() {
      const p = Q(".plateau"); if (!S.att.size) { p.classList.remove("o"); return; }
      const i = impact();
      p.innerHTML = '<div class="t"><b>' + S.att.size + " changement" + (S.att.size > 1 ? "s" : "") + ' en attente</b><div class="note">' + (i.act.length ? "+ " + i.act.map(nom).map(esc).join(", ") : "") + (i.act.length && i.des.length ? " · " : "") + (i.des.length ? "− " + i.des.map(nom).map(esc).join(", ") : "") + "</div>" +
        (i.bloc.length ? '<div class="note" style="color:var(--danger)">Bloqué : ' + i.bloc.map((b) => esc(nom(b[0])) + " est utilisé par " + esc(nom(b[1]))).join(" ; ") + "</div>" : "") + '</div><button class="btn" data-a="annuler">Annuler</button><button class="btn" data-a="impact">Voir l’impact</button><button class="btn pri" data-a="appliquer"' + (i.bloc.length || S.occupe ? " disabled" : "") + ">Appliquer</button>";
      p.classList.add("o");
    }
    function tiroir(id, silencieux) {
      const m = par(id); if (!m) return; S.sel = id;
      const c = crit(m), contr = (x) => ((m.contraintes || []).find((k) => k[0] === x) || [])[1] || "";
      const chip = (x) => '<button class="chip' + ((par(x) || {}).etat === "actif" ? "" : " off") + '" data-ouvre="' + esc(x) + '"><i></i>' + esc(nom(x)) + (contr(x) ? ' <span class="note mono">' + esc(contr(x)) + "</span>" : "") + "</button>";
      const dep = actifsApres(id), p = m.permissions || {}, lock = verrou(m) && !(m.etat === "actif" && !m.essentiel && gere() && (m.requis_par || []).length), on = voulu(id);
      const bas = lock ? "" : '<button class="btn ' + (on ? "dng" : "pri") + '" data-a="bas2" data-id="' + esc(id) + '">' + (S.att.has(id) ? "Annuler le changement" : on ? "Désactiver" : "Activer") + "</button>";
      const hors = ((p.reseau || []).map((r) => "<div><span>Se connecte à : " + esc(r) + "</span></div>").join("")) + ((p.ecritures || []).map((r) => "<div><span>Écrit dans : " + esc(r) + "</span></div>").join("")) + ((p.privileges || []).map((r) => "<div><span>Privilège : " + esc(r) + "</span></div>").join(""));
      Q(".tiroir").innerHTML = '<div class="th"><div class="l1">' + ico(m.famille) + '<div style="min-width:0"><h2>' + esc(m.nom) + '</h2><div class="note mono">' + esc(m.id) + (m.version ? " · v" + esc(m.version) : "") + '</div></div><button class="x" data-a="ferme" aria-label="Fermer">×</button></div>' +
        '<div style="display:flex;gap:6px;flex-wrap:wrap"><span class="p ' + (m.etat === "actif" ? "ok" : m.etat === "refuse" ? "dg" : m.etat === "a_installer" ? "al" : "nu") + '">' + (m.etat === "actif" ? "Actif" : m.etat === "a_installer" ? "À installer" : m.etat === "refuse" ? "Refusé" : "Inactif") + '</span><span class="p nu">' + esc(U.famLib(m.famille || "autres")) + "</span>" + (m.confiance ? '<span class="p nu">confiance ' + esc(m.confiance) + "</span>" : "") + "</div></div>" +
        '<div class="tc"><p>' + esc(m.description || "") + "</p>" +
        (m.etat === "a_installer" ? '<div class="bandeau al">Un script d’installation du module est à lancer sur la machine, puis le module s’active.</div>' : "") +
        '<div><div class="lib">Et sans lui ?</div><div class="sans ' + c + '">' + (c ? '<div><span class="p ' + CRIT[c][1] + '">' + CRIT[c][0] + '</span> <span class="note">' + esc(CRIT[c][2]) + "</span></div>" : '<div class="note">Importance non déclarée par ce module.</div>') +
        (m.sans ? "<div>" + esc(m.sans) + "</div>" : "") + (dep.length ? '<div class="note">S’arrêteraient avec lui : <b>' + dep.map(nom).map(esc).join(", ") + "</b>.</div>" : "") + "</div></div>" +
        '<div><div class="lib">Il compte</div><div class="cles"><div class="cle"><b>' + (m.capacites != null ? m.capacites : "—") + "</b><span>capacités</span></div><div class=\"cle\"><b>" + (m.detecteurs || 0) + "</b><span>détecteurs</span></div><div class=\"cle\"><b>" + (m.moteurs || 0) + "</b><span>moteurs</span></div></div></div>" +
        '<div><div class="lib">Dépendances</div><div class="dep"><div class="rang">' + ((m.requiert || []).length ? "Il a besoin de : " + m.requiert.map(chip).join("") : "<span>Il ne dépend d’aucun autre module.</span>") + '</div><div class="fleche">↓</div><div class="centre">' + esc(m.nom) + '</div><div class="fleche">↓</div><div class="rang">' + ((m.requis_par || []).length ? "Utilisé par : " + m.requis_par.map(chip).join("") : "<span>Aucun autre module ne s’appuie sur lui.</span>") + "</div></div></div>" +
        ((m.conflits || []).length || (m.suggere || []).length || (m.fournit || []).length ? '<div><div class="lib">Compagnie</div><div class="dep">' +
          ((m.conflits || []).length ? '<div class="rang">Refuse la compagnie de : ' + m.conflits.map((x) => '<span class="p dg">' + esc(nom(x)) + "</span>").join(" ") + "</div>" : "") +
          ((m.suggere || []).length ? '<div class="rang">Sert mieux avec : ' + m.suggere.map(chip).join("") + "</div>" : "") +
          ((m.fournit || []).length ? '<div class="rang">Rend le service : ' + m.fournit.map((x) => '<span class="p ac">' + esc(x) + "</span>").join(" ") + "</div>" : "") + "</div></div>" : "") +
        '<div><div class="lib">Ce qu’il peut faire hors de lui</div><div class="perms">' + (hors || '<div class="note">Rien : ni réseau, ni écriture déclarés.</div>') + "</div></div>" +
        '<p class="note">Désactiver un module retire ses menus, ses capacités et ses moteurs ; <b>ses données restent</b> et reviennent à la réactivation.</p></div>' +
        '<div class="tp"><button class="btn" data-a="cons" data-id="' + esc(id) + '"' + (m.etat === "actif" ? "" : " disabled") + '>Ouvrir la console</button><button class="btn" data-a="reg" data-id="' + esc(id) + '"' + (m.etat === "actif" ? "" : " disabled") + '>Réglages</button><span class="sp"></span>' + bas + "</div>";
      Q(".tiroir").classList.add("o"); Q(".voile").classList.add("o");
      if (m.etat === "actif" && !silencieux) {                                  // la santé se lit à l'ouverture : un verdict, et de quoi se plaindre
        agir_sante(id).then((sa) => {
          const tags = Q(".tiroir .th > div:last-child");
          if (!sa || !tags || S.sel !== id) return;
          const cls = sa.verdict === "sain" ? "ok" : sa.verdict === "en_echec" ? "dg" : "al";
          tags.insertAdjacentHTML("beforeend", '<span class="p ' + cls + '" title="' + esc((sa.en_echec || []).concat(sa.a_surveiller || []).join(", ")) + '">' + (sa.verdict === "sain" ? "en bonne santé" : sa.verdict === "en_echec" ? "en échec" : "à surveiller") + "</span>");
        });
      }
    }
    const agir_sante = (id) => CASS.agir("modules.sante", { module: id }).catch(() => null);
    function fermerTiroir() { S.sel = null; Q(".tiroir").classList.remove("o"); if (!Q(".feuille").classList.contains("o")) Q(".voile").classList.remove("o"); }
    function fermerFeuille() { Q(".feuille").classList.remove("o"); if (!Q(".tiroir").classList.contains("o")) Q(".voile").classList.remove("o"); }
    function fermerTout() { if (Q(".feuille").classList.contains("o")) fermerFeuille(); else fermerTiroir(); }

    function feuille() {
      const i = impact(), f = Q(".feuille");
      const ligne = (s, cl, t, d) => '<div class="ligne"><span class="signe ' + cl + '">' + s + "</span><div><b>" + esc(t) + '</b><div class="note">' + d + "</div></div></div>";
      const vitaux = i.des.filter((id) => par(id).importance === "vital");
      f.innerHTML = "<h2>Ce que ces changements vont faire</h2><div>" +
        i.act.map((id) => ligne("+", "plus", "Activer " + nom(id), S.att.has(id) ? "Demandé par vous. Branche " + (par(id).capacites != null ? par(id).capacites + " capacités, " : "") + (par(id).detecteurs || 0) + " détecteur" + ((par(id).detecteurs || 0) > 1 ? "s" : "") + " et " + (par(id).moteurs || 0) + " moteur" + ((par(id).moteurs || 0) > 1 ? "s" : "") + "." : "Activé aussi : " + esc(nom(id)) + " est requis par un module que vous activez.")).join("") +
        i.des.map((id) => ligne("−", "moins", "Désactiver " + nom(id), esc(par(id).sans || "Retire ses menus, capacités et moteurs.") + " Ses données restent.")).join("") + "</div>" +
        (vitaux.length ? '<div class="bandeau">Attention : ' + vitaux.map((id) => esc(nom(id))).join(", ") + " est déclaré vital : la maison peut ne plus tenir sans lui.</div>" : "") +
        (i.bloc.length ? '<div class="bandeau">Impossible tel quel : ' + i.bloc.map((b) => esc(nom(b[0])) + " est utilisé par " + esc(nom(b[1]))).join(" ; ") + ". Désactivez aussi ces modules, ou annulez.</div>" : "") +
        '<p class="note" style="margin:0">Rien n’est appliqué avant votre accord. Chaque activation est prouvée et se défait d’un clic.</p><div style="display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap">' +
        '<button class="btn" data-a="retour">Retour</button>' + (i.bloc.length ? '<button class="btn" data-a="cascade">Désactiver aussi ces modules</button>' : "") + '<button class="btn pri" data-a="appliquer"' + (i.bloc.length || S.occupe ? " disabled" : "") + ">Appliquer</button></div>";
      f.classList.add("o"); Q(".voile").classList.add("o");
    }
    async function appliquer() {
      if (S.occupe) return; const i = impact(); if (i.bloc.length) return;
      S.occupe = true; plateau(); fermerFeuille();
      let fait = 0;
      try {
        // les désactivations d'abord, les dépendants avant leurs dépendances ; puis les activations, qui tirent leurs dépendances
        const ordre = [], reste = new Set(i.des);                         // un module ne se désactive qu'après tous ceux qui s'appuient sur lui
        while (reste.size) {
          const pret = [...reste].filter((id) => !(par(id).requis_par || []).some((r) => reste.has(r)));
          if (!pret.length) { pret.push([...reste][0]); }                 // un cycle ne devrait pas exister : on avance quand même, le serveur tranchera
          pret.forEach((id) => { ordre.push(id); reste.delete(id); });
        }
        for (const id of ordre) { await CASS.agir("modules.desactiver", { module: id, cascade: false }); fait++; }
        for (const id of i.act.filter((x) => S.att.get(x))) { await CASS.agir("modules.activer", { module: id, avec_dependances: true }); fait++; }
        dire(fait + " changement" + (fait > 1 ? "s appliqués" : " appliqué"), "ok");
      } catch (e) { dire((fait ? fait + " fait(s), puis : " : "") + (e.message || e), "err"); }
      S.att.clear(); S.occupe = false;
      try { await U.lire(); } catch (e) { /* le catalogue se relira à la prochaine ouverture */ }
      if (ctx && ctx.rendre) { await ctx.rendre(false); } else dessiner();
    }
    function surClic(e) {
      const b = e.target.closest("[data-a],[data-ouvre]"); if (!b) return;
      if (b.dataset.ouvre) { tiroir(b.dataset.ouvre); return; }
      const a = b.dataset.a;
      if (a === "ferme") fermerTiroir();
      else if (a === "annuler") { S.att.clear(); dessiner(); }
      else if (a === "impact") feuille();
      else if (a === "retour") fermerFeuille();
      else if (a === "appliquer") appliquer();
      else if (a === "bas2") { bascule(b.dataset.id, !voulu(b.dataset.id)); }
      else if (a === "cons") { const m = par(b.dataset.id); if (CASS.ouvrirConsole) CASS.ouvrirConsole(m.id, m.nom); }
      else if (a === "reg") reglages(b.dataset.id);
      else if (a === "cascade") { impact().bloc.forEach((x) => S.att.set(x[1], false)); dessiner(); feuille(); }
    }
    document.addEventListener("keydown", function cle(e) { if (!document.body.contains(sur)) { document.removeEventListener("keydown", cle); return; } if (e.key === "Escape") fermerTout(); });

    surcouches();
    dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : le dessin de la page et ses gestes.
// EC : néant.
// LIEN : interface/CN_modules-ui.js (le catalogue, qui appelle cette page), interface/CN_console-module.js (la console où mènent l'engrenage et le bouton Ouvrir), noyau/CN_manifeste.py (importance et sans).
