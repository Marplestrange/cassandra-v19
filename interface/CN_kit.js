// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Le kit commun des écrans V19 : la feuille de style, les icônes, les petits composants (pas
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #8c33bc
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Le kit commun des écrans V19 : la feuille de style, les icônes, les petits composants (pastille, titre, « il y a »), la fenêtre de confirmation.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=8c33bc ▼▼▼
// Le kit commun des écrans V19 : la feuille de style, les icônes, les petits composants (pastille, titre, « il y a »), la fenêtre de confirmation.
// Chaque écran se met dans un <div class="kit"> ; la feuille s'injecte UNE fois (id kit-css). La Logithèque l'a inauguré ; les écrans suivants le réemploient.
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const I = {
    vue: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    inst: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><path d="M16.5 13v7M13 16.5h7"/>',
    shop: '<path d="M4 8h16l-1.2 11a2 2 0 01-2 1.8H7.2a2 2 0 01-2-1.8L4 8z"/><path d="M8 8V6a4 4 0 018 0v2"/>',
    maj: '<path d="M20 12a8 8 0 10-2.4 5.7"/><path d="M20 5v7h-7"/>',
    src: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3.2 3 3.2 15 0 18M12 3c-3.2 3-3.2 15 0 18"/>',
    sec: '<path d="M12 3l8 4v5c0 4.4-3.1 7.6-8 9-4.9-1.4-8-4.6-8-9V7z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    sante: '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>', jour: '<path d="M12 7v5l3 2"/><circle cx="12" cy="12" r="9"/>',
    dev: '<path d="M8 8l-5 4 5 4M16 8l5 4-5 4M14 5l-4 14"/>', reg: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
    bot: '<rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01"/>', check: '<path d="M5 12l4.5 4.5L19 7"/>',
    warn: '<path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18v.01"/>', shield: '<path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3z"/>',
    lock: '<rect x="5" y="10" width="14" height="10" rx="2.5"/><path d="M8 10V7a4 4 0 018 0v3"/>', eye: '<path d="M3 12s3.5-7 9-7 9 7 9 7-3.5 7-9 7-9-7-9-7z"/><circle cx="12" cy="12" r="3"/>',
    box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>', chev: '<path d="M6 9l6 6 6-6"/>', pause: '<path d="M9 6v12M15 6v12"/>',
  };
  const ic = (k, c) => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"' + (c ? ' class="' + c + '"' : "") + ' aria-hidden="true">' + (I[k] || I.box) + "</svg>";
  const CSS = ".kit{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.kit *{box-sizing:border-box}.kit h1,.kit h2,.kit h3,.kit h4,.kit p{margin:0}" +
    ".kit .note{font-size:12.5px;color:var(--txt-soft)}.kit .faint{color:var(--txt-faint)}.kit .mono{font-family:ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace;overflow-wrap:anywhere}" +
    ".kit .btn,.kit-t .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 14px;font:600 13px 'Inter',system-ui,sans-serif;cursor:pointer;white-space:nowrap}" +
    ".kit .btn:hover:not([disabled]),.kit-t .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.kit .btn.pri,.kit-t .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}" +
    ".kit .btn.pri:hover:not([disabled]),.kit-t .btn.pri:hover:not([disabled]){color:var(--on-accent,#fff);filter:brightness(1.08)}.kit .btn.dng,.kit-t .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}" +
    ".kit .btn.mini,.kit-t .btn.mini{padding:4px 10px;font-size:12px}.kit .btn[disabled],.kit-t .btn[disabled]{opacity:.45;cursor:not-allowed}.kit :focus-visible,.kit-t :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}" +
    ".kit .carte{background:var(--surface);backdrop-filter:blur(14px) saturate(150%);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);padding:14px 16px;display:flex;flex-direction:column;gap:10px;min-width:0}" +
    ".kit .carte h3{font:650 15px/1.25 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.kit .carte h4{font:650 13.5px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".kit .g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.kit .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}" +
    ".kit .p{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:3px 8px;font:600 11px/1.2 'Inter',sans-serif;background:color-mix(in srgb,var(--txt-soft) 10%,transparent);color:var(--txt-soft);white-space:nowrap}" +
    ".kit .p svg,.kit-t .p svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.kit .p.ok,.kit-t .p.ok{background:color-mix(in srgb,var(--ok) 13%,transparent);color:var(--ok)}" +
    ".kit .p.al,.kit-t .p.al{background:color-mix(in srgb,var(--warn) 15%,transparent);color:var(--warn)}.kit .p.dg,.kit-t .p.dg{background:color-mix(in srgb,var(--danger) 13%,transparent);color:var(--danger)}" +
    ".kit .p.ac{background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent)}.kit .p.vi,.kit-t .p.vi{background:var(--txt-strong,#111);color:var(--bg,#fff)}" +
    ".kit .ico,.kit-t .ico{flex:none;width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent)}.kit .ico svg,.kit-t .ico svg{width:20px;height:20px}" +
    ".kit .ico.off{background:var(--line);color:var(--txt-faint)}.kit .ico.sm{width:30px;height:30px;border-radius:9px}.kit .ico.sm svg{width:16px;height:16px}.kit .ico.al{background:color-mix(in srgb,var(--warn) 15%,transparent);color:var(--warn)}" +
    ".kit .sw{position:relative;width:38px;height:22px;flex:none;border-radius:999px;border:0;background:var(--line-strong,var(--line));cursor:pointer;padding:0}.kit .sw::after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .15s}" +
    ".kit .sw.on{background:var(--accent)}.kit .sw.on::after{transform:translateX(16px)}.kit .sw[disabled]{opacity:.45;cursor:not-allowed}" +
    ".kit .barre{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}.kit .barre input[type=search]{flex:1 1 240px;min-width:0;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 12px;font:500 13px 'Inter',sans-serif}" +
    ".kit .sel{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 12px;font:600 13px 'Inter',sans-serif;cursor:pointer;min-width:0;max-width:100%}" +
    ".kit .seg{display:inline-flex;border:1px solid var(--line-strong,var(--line));border-radius:10px;overflow:hidden;background:var(--surface-solid,var(--surface));max-width:100%;overflow-x:auto}.kit .seg button{border:0;background:transparent;padding:6px 12px;font:600 12.5px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer;white-space:nowrap}" +
    ".kit .seg button.on{background:var(--accent);color:var(--on-accent,#fff)}.kit .seg .cnt{opacity:.65;margin-left:4px;font-size:11px}" +
    ".kit .rub{display:flex;flex-direction:column;gap:10px}.kit .rub-t{display:flex;gap:10px;align-items:center;border:0;background:transparent;cursor:pointer;width:100%;text-align:left;padding:4px 2px 9px;border-bottom:1px solid var(--line);color:var(--txt)}" +
    ".kit .rub-t h3{font:650 15px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.kit .rub-t .chev{margin-left:auto;width:18px;height:18px;color:var(--txt-faint);transition:transform .15s}.kit .rub-t .chev.ferme{transform:rotate(-90deg)}" +
    ".kit .mod{cursor:pointer;gap:9px}.kit .mod.off{opacity:.82}.kit .mod .l1{display:flex;gap:11px;align-items:center}.kit .mod .sp{flex:1;min-width:0}.kit .mod h3{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".kit .mod .desc{font-size:12.5px;color:var(--txt-soft);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.kit .pied{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:auto;padding-top:9px;border-top:1px solid var(--line)}" +
    ".kit .hero{padding:16px 18px;border-color:color-mix(in srgb,var(--accent) 30%,transparent)}.kit .hero .l1{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}.kit .hero h2{font:700 20px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".kit .demande{display:flex;gap:8px}.kit .demande input{flex:1;min-width:0;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:11px;padding:10px 13px;font:14px 'Inter',sans-serif}" +
    ".kit .chips{display:flex;gap:6px;flex-wrap:wrap}.kit .chip{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;font:600 12.5px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer}" +
    ".kit .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.kit .stat{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:2px;text-align:left}" +
    ".kit .stat b{font:650 26px/1.1 ui-monospace,Menlo,monospace;color:var(--txt-strong,var(--txt))}.kit .stat span{font-size:12.5px;color:var(--txt-soft)}.kit .stat.al b{color:var(--warn)}.kit .stat.ok b{color:var(--ok)}" +
    ".kit .onglets{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto}.kit .onglets button{border:0;background:transparent;padding:9px 14px;font:600 13px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}.kit .onglets button.on{color:var(--accent);border-bottom-color:var(--accent)}" +
    ".kit .grille-m{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.kit .jauge{height:8px;border-radius:99px;background:var(--line);overflow:hidden}.kit .jauge i{display:block;height:100%;background:var(--accent);border-radius:99px}.kit .jauge.al i{background:var(--warn)}.kit .jauge.dg i{background:var(--danger)}" +
    ".kit .liste{display:flex;flex-direction:column}.kit .li{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid var(--line);flex-wrap:wrap}.kit .li:first-child{border-top:0}.kit .li .sp{flex:1;min-width:180px}.kit .li .sp b{color:var(--txt-strong,var(--txt))}.kit .li .note{display:block}" +
    ".kit .pourquoi{display:flex;gap:6px;align-items:flex-start;font-size:11.5px;color:var(--info,var(--accent));margin-top:2px}.kit .pourquoi svg{width:13px;height:13px;flex:none;margin-top:2px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}" +
    ".kit .alerte{border:1px solid var(--line);border-left-width:4px;border-radius:12px;padding:10px 14px;background:var(--surface);display:flex;gap:12px;align-items:center;flex-wrap:wrap}.kit .alerte.al{border-left-color:var(--warn)}.kit .alerte.dg{border-left-color:var(--danger)}.kit .alerte.in{border-left-color:var(--accent)}" +
    ".kit .alerte .sp{flex:1;min-width:220px}.kit .radio{display:flex;gap:11px;align-items:flex-start;padding:11px 13px;border:1px solid var(--line);border-radius:12px;cursor:pointer;background:var(--surface);text-align:left;color:var(--txt);font:inherit;width:100%}" +
    ".kit .radio.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}.kit .radio i{flex:none;width:16px;height:16px;border-radius:50%;border:2px solid var(--line-strong,var(--line));margin-top:3px}.kit .radio.on i{border-color:var(--accent);background:radial-gradient(var(--accent) 45%,transparent 50%)}" +
    ".kit .vide{padding:28px 10px;text-align:center;color:var(--txt-soft)}.kit .titre h1{font:650 20px/1.2 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.kit .titre p{color:var(--txt-soft);margin-top:3px;max-width:68ch}" +
    ".kit .avance{margin-bottom:0}.kit .carte.pret{align-items:flex-start}" +
    ".kit-m{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(520px,calc(100% - 32px));max-height:calc(100vh - 40px);overflow:auto;background:var(--bg);border:1px solid var(--line-strong,var(--line));border-radius:18px;z-index:10000;box-shadow:0 30px 80px -20px rgba(0,0,0,.5);padding:20px;display:flex;flex-direction:column;gap:14px;color:var(--txt);font-size:13.5px;line-height:1.5}" +
    ".kit-m h2{margin:0;font:650 19px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.kit-m .note{font-size:12.5px;color:var(--txt-soft)}.kit-m .acts{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}.kit-m .lst{margin:0;padding-left:18px}" +
    ".kit-m .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 14px;font:600 13px 'Inter',system-ui,sans-serif;cursor:pointer}.kit-m .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.kit-m .btn.dng{color:var(--danger)}" +
    ".kit .choix{text-align:left;cursor:pointer;position:relative;font:inherit;color:inherit;gap:6px}.kit .choix .coche{position:absolute;top:12px;right:12px;width:22px;height:22px;border-radius:7px;border:2px solid var(--line-strong,var(--line));display:grid;place-items:center;color:transparent}.kit .choix .coche svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}" +
    ".kit .choix.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}.kit .choix.on .coche{background:var(--accent);border-color:var(--accent);color:var(--on-accent,#fff)}.kit .accueil{padding:20px}.kit .accueil h2{font:700 22px/1.2 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".kit-v{position:fixed;inset:0;background:rgba(5,20,18,.42);backdrop-filter:blur(3px);z-index:9998}" +
    ".kit-t{position:fixed;top:0;right:0;bottom:0;width:min(520px,100%);background:var(--bg);border-left:1px solid var(--line-strong,var(--line));z-index:9999;display:flex;flex-direction:column;box-shadow:-20px 0 50px -20px rgba(0,0,0,.4);color:var(--txt);font-size:13.5px;line-height:1.5}" +
    ".kit-t *{box-sizing:border-box}.kit-t .tete{padding:18px 20px 0;display:flex;flex-direction:column;gap:12px}.kit-t .corps{padding:16px 20px 24px;overflow:auto;display:flex;flex-direction:column;gap:14px;flex:1}.kit-t h2{margin:0;font:650 19px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".kit-t .onglets{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto}.kit-t .onglets button{border:0;background:transparent;padding:9px 12px;font:600 13px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}.kit-t .onglets button.on{color:var(--accent);border-bottom-color:var(--accent)}" +
    ".kit-t .pied{padding:12px 20px calc(12px + env(safe-area-inset-bottom,0px));border-top:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap}.kit-t .carte{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}" +
    ".kit-t .lib{font:600 10.5px 'Inter',sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}.kit-t .note{font-size:12.5px;color:var(--txt-soft)}.kit-t .mono{font-family:ui-monospace,Menlo,monospace}.kit-t .reglage{display:flex;gap:14px;align-items:center}.kit-t .reglage .sp{flex:1}" +
    ".kit-t .sw{position:relative;width:38px;height:22px;flex:none;border-radius:999px;border:0;background:var(--line-strong,var(--line));cursor:pointer;padding:0}.kit-t .sw::after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .15s}.kit-t .sw.on{background:var(--accent)}.kit-t .sw.on::after{transform:translateX(16px)}" +
    "@media(max-width:860px){.kit-t{top:auto;height:88vh;width:100%;border-left:0;border-top:1px solid var(--line-strong,var(--line));border-radius:20px 20px 0 0}.kit .demande{flex-direction:column}.kit .demande .btn{width:100%}.kit .g2,.kit .grille{grid-template-columns:minmax(0,1fr)}}" +
    "@media (prefers-reduced-motion:reduce){.kit *,.kit-t *{transition:none!important}}";
  const depuis = (ts) => { const s = Math.max(0, Date.now() / 1000 - ts); if (s < 90) return "à l’instant"; if (s < 3600) return "il y a " + Math.round(s / 60) + " min"; if (s < 86400) return "il y a " + Math.round(s / 3600) + " h"; return new Date(ts * 1000).toLocaleDateString("fr-FR"); };
  const pill = (t, c, i) => '<span class="p ' + (c || "") + '">' + (i ? ic(i) : "") + esc(t) + "</span>";
  const titre = (t, d, act) => '<div class="barre"><div class="titre" style="flex:1 1 260px;min-width:0"><h1>' + esc(t) + "</h1><p>" + esc(d) + "</p></div>" + (act || "") + "</div>";
  const injecter = () => { if (document.getElementById("kit-css")) return; const st = document.createElement("style"); st.id = "kit-css"; st.textContent = CSS; document.head.appendChild(st); };
  // « Es-tu sûr ? » : une fenêtre qui rend une promesse (vrai si on confirme). `corps` est du HTML déjà échappé par l'appelant.
  function confirmer(titreF, corps, oui, danger) {
    return new Promise((fin) => {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999;
      const m = document.createElement("div"); m.className = "kit-m"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.setAttribute("aria-label", titreF);
      m.innerHTML = "<h2>" + esc(titreF) + "</h2>" + corps + '<div class="acts"><button class="btn" data-c="non">Annuler</button><button class="btn ' + (danger ? "dng" : "pri") + '" data-c="oui">' + esc(oui) + "</button></div>";
      const clore = (r) => { v.remove(); m.remove(); fin(r); };
      v.addEventListener("click", () => clore(false)); m.addEventListener("click", (e) => { const b = e.target.closest("[data-c]"); if (b) clore(b.dataset.c === "oui"); });
      m.addEventListener("keydown", (e) => { if (e.key === "Escape") clore(false); });
      document.body.appendChild(v); document.body.appendChild(m); const f = m.querySelector("[data-c=non]"); if (f) f.focus();
    });
  }
  const agir = (c, a) => CASS.agir(c, a || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };
  CASS.kit = { esc: esc, I: I, ic: ic, pill: pill, depuis: depuis, titre: titre, injecter: injecter, confirmer: confirmer, agir: agir, dire: dire };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
