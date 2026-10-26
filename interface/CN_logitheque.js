// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : La Logithèque : où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de C
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #8ef991
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : La Logithèque : où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de Cassandra sur eux.
// MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=8ef991 ▼▼▼
// La Logithèque : où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de Cassandra sur eux.
// Une page, des sections (Vue d'ensemble, Installés, Mises à jour, Boutique, Sources, Sécurité, Santé, Journal, Développeur, Réglages).
// Principe : Cassandra gère les modules SEULE ; l'utilisateur voit ce qu'elle fait (le récit, avec le pourquoi), peut tout défaire,
// la mettre en pause, verrouiller un module, ou lui demander. Les gestes directs (interrupteurs, retrait) sont derrière un « Mode avancé ».
(function () {
  "use strict";
  const CASS = window.CASS;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const agir = (c, a) => CASS.agir(c, a || {});
  const dire = (t, k) => { if (typeof window.toast === "function") window.toast(t, k); };

  const SECTIONS = [["vue", "Vue d’ensemble", "vue"], ["inst", "Installés", "inst"], ["maj", "Mises à jour", "maj"], ["shop", "Boutique", "shop"], ["src", "Sources", "src"],
    ["sec", "Sécurité et confiance", "sec"], ["sante", "Santé", "sante"], ["jour", "Journal et versions", "jour"], ["dev", "Développeur", "dev"], ["reg", "Réglages", "reg"]];
  const PRETES = ["vue", "inst", "shop"];                         // les sections portées ; les autres renvoient vers les pages qui existent déjà

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

  const IMP = { vital: ["Vital", "vi"], important: ["Important", "al"], optionnel: ["Optionnel", ""] };
  const NIV = {
    observer: ["Observer", "Je regarde et je te raconte ce que je ferais. Je ne touche à rien."],
    entretien: ["Entretien", "Je retire ce qui est révoqué, je prends les mises à jour sans permission en plus, je mets en pause ce qui échoue."],
    reine: ["Reine", "Je gère tout : j’ajoute, je mets à jour, je retire, j’active. Tu n’as rien à faire."],
  };
  const FENETRES = { nuit: "La nuit, 02:00–05:00", dimanche: "Dimanche matin", hors_bureau: "Hors heures de bureau", tout: "À tout moment" };
  const GESTES = { active: "a activé", desactive: "a désactivé", installe: "a installé", retour: "a remis une version précédente de", desinstalle: "a retiré" };

  const CSS = ".lg{display:flex;flex-direction:column;gap:16px;color:var(--txt);font-size:13.5px;line-height:1.5}.lg *{box-sizing:border-box}.lg h1,.lg h2,.lg h3,.lg h4,.lg p{margin:0}" +
    ".lg .note{font-size:12.5px;color:var(--txt-soft)}.lg .faint{color:var(--txt-faint)}.lg .mono{font-family:ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace;overflow-wrap:anywhere}" +
    ".lg .btn,.lgt .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:7px 14px;font:600 13px 'Inter',system-ui,sans-serif;cursor:pointer;white-space:nowrap}" +
    ".lg .btn:hover:not([disabled]),.lgt .btn:hover:not([disabled]){border-color:var(--accent);color:var(--accent)}.lg .btn.pri,.lgt .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}" +
    ".lg .btn.pri:hover:not([disabled]),.lgt .btn.pri:hover:not([disabled]){color:var(--on-accent,#fff);filter:brightness(1.08)}.lg .btn.dng,.lgt .btn.dng{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,transparent)}" +
    ".lg .btn.mini,.lgt .btn.mini{padding:4px 10px;font-size:12px}.lg .btn[disabled],.lgt .btn[disabled]{opacity:.45;cursor:not-allowed}.lg :focus-visible,.lgt :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}" +
    ".lg .carte{background:var(--surface);backdrop-filter:blur(14px) saturate(150%);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-glass);padding:14px 16px;display:flex;flex-direction:column;gap:10px;min-width:0}" +
    ".lg .carte h3{font:650 15px/1.25 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.lg .carte h4{font:650 13.5px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".lg .g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.lg .grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}" +
    ".lg .p{display:inline-flex;align-items:center;gap:5px;border-radius:7px;padding:3px 8px;font:600 11px/1.2 'Inter',sans-serif;background:color-mix(in srgb,var(--txt-soft) 10%,transparent);color:var(--txt-soft);white-space:nowrap}" +
    ".lg .p svg,.lgt .p svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.lg .p.ok,.lgt .p.ok{background:color-mix(in srgb,var(--ok) 13%,transparent);color:var(--ok)}" +
    ".lg .p.al,.lgt .p.al{background:color-mix(in srgb,var(--warn) 15%,transparent);color:var(--warn)}.lg .p.dg,.lgt .p.dg{background:color-mix(in srgb,var(--danger) 13%,transparent);color:var(--danger)}" +
    ".lg .p.ac{background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent)}.lg .p.vi,.lgt .p.vi{background:var(--txt-strong,#111);color:var(--bg,#fff)}" +
    ".lg .ico,.lgt .ico{flex:none;width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent)}.lg .ico svg,.lgt .ico svg{width:20px;height:20px}" +
    ".lg .ico.off{background:var(--line);color:var(--txt-faint)}.lg .ico.sm{width:30px;height:30px;border-radius:9px}.lg .ico.sm svg{width:16px;height:16px}.lg .ico.al{background:color-mix(in srgb,var(--warn) 15%,transparent);color:var(--warn)}" +
    ".lg .sw{position:relative;width:38px;height:22px;flex:none;border-radius:999px;border:0;background:var(--line-strong,var(--line));cursor:pointer;padding:0}.lg .sw::after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .15s}" +
    ".lg .sw.on{background:var(--accent)}.lg .sw.on::after{transform:translateX(16px)}.lg .sw[disabled]{opacity:.45;cursor:not-allowed}" +
    ".lg .barre{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}.lg .barre input[type=search]{flex:1 1 240px;min-width:0;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 12px;font:500 13px 'Inter',sans-serif}" +
    ".lg .sel{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:10px;padding:8px 12px;font:600 13px 'Inter',sans-serif;cursor:pointer;min-width:0;max-width:100%}" +
    ".lg .seg{display:inline-flex;border:1px solid var(--line-strong,var(--line));border-radius:10px;overflow:hidden;background:var(--surface-solid,var(--surface));max-width:100%;overflow-x:auto}.lg .seg button{border:0;background:transparent;padding:6px 12px;font:600 12.5px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer;white-space:nowrap}" +
    ".lg .seg button.on{background:var(--accent);color:var(--on-accent,#fff)}.lg .seg .cnt{opacity:.65;margin-left:4px;font-size:11px}" +
    ".lg .rub{display:flex;flex-direction:column;gap:10px}.lg .rub-t{display:flex;gap:10px;align-items:center;border:0;background:transparent;cursor:pointer;width:100%;text-align:left;padding:4px 2px 9px;border-bottom:1px solid var(--line);color:var(--txt)}" +
    ".lg .rub-t h3{font:650 15px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.lg .rub-t .chev{margin-left:auto;width:18px;height:18px;color:var(--txt-faint);transition:transform .15s}.lg .rub-t .chev.ferme{transform:rotate(-90deg)}" +
    ".lg .mod{cursor:pointer;gap:9px}.lg .mod.off{opacity:.82}.lg .mod .l1{display:flex;gap:11px;align-items:center}.lg .mod .sp{flex:1;min-width:0}.lg .mod h3{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".lg .mod .desc{font-size:12.5px;color:var(--txt-soft);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.lg .pied{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:auto;padding-top:9px;border-top:1px solid var(--line)}" +
    ".lg .hero{padding:16px 18px;border-color:color-mix(in srgb,var(--accent) 30%,transparent)}.lg .hero .l1{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}.lg .hero h2{font:700 20px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".lg .demande{display:flex;gap:8px}.lg .demande input{flex:1;min-width:0;border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));color:var(--txt);border-radius:11px;padding:10px 13px;font:14px 'Inter',sans-serif}" +
    ".lg .chips{display:flex;gap:6px;flex-wrap:wrap}.lg .chip{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;font:600 12.5px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer}" +
    ".lg .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.lg .stat{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:2px;text-align:left}" +
    ".lg .stat b{font:650 26px/1.1 ui-monospace,Menlo,monospace;color:var(--txt-strong,var(--txt))}.lg .stat span{font-size:12.5px;color:var(--txt-soft)}.lg .stat.al b{color:var(--warn)}.lg .stat.ok b{color:var(--ok)}" +
    ".lg .liste{display:flex;flex-direction:column}.lg .li{display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid var(--line);flex-wrap:wrap}.lg .li:first-child{border-top:0}.lg .li .sp{flex:1;min-width:180px}.lg .li .sp b{color:var(--txt-strong,var(--txt))}.lg .li .note{display:block}" +
    ".lg .pourquoi{display:flex;gap:6px;align-items:flex-start;font-size:11.5px;color:var(--info,var(--accent));margin-top:2px}.lg .pourquoi svg{width:13px;height:13px;flex:none;margin-top:2px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}" +
    ".lg .alerte{border:1px solid var(--line);border-left-width:4px;border-radius:12px;padding:10px 14px;background:var(--surface);display:flex;gap:12px;align-items:center;flex-wrap:wrap}.lg .alerte.al{border-left-color:var(--warn)}.lg .alerte.dg{border-left-color:var(--danger)}.lg .alerte.in{border-left-color:var(--accent)}" +
    ".lg .alerte .sp{flex:1;min-width:220px}.lg .radio{display:flex;gap:11px;align-items:flex-start;padding:11px 13px;border:1px solid var(--line);border-radius:12px;cursor:pointer;background:var(--surface);text-align:left;color:var(--txt);font:inherit;width:100%}" +
    ".lg .radio.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}.lg .radio i{flex:none;width:16px;height:16px;border-radius:50%;border:2px solid var(--line-strong,var(--line));margin-top:3px}.lg .radio.on i{border-color:var(--accent);background:radial-gradient(var(--accent) 45%,transparent 50%)}" +
    ".lg .vide{padding:28px 10px;text-align:center;color:var(--txt-soft)}.lg .titre h1{font:650 20px/1.2 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.lg .titre p{color:var(--txt-soft);margin-top:3px;max-width:68ch}" +
    ".lg .avance{margin-bottom:0}.lg .carte.pret{align-items:flex-start}" +
    ".lgv{position:fixed;inset:0;background:rgba(5,20,18,.42);backdrop-filter:blur(3px);z-index:9998}" +
    ".lgt{position:fixed;top:0;right:0;bottom:0;width:min(520px,100%);background:var(--bg);border-left:1px solid var(--line-strong,var(--line));z-index:9999;display:flex;flex-direction:column;box-shadow:-20px 0 50px -20px rgba(0,0,0,.4);color:var(--txt);font-size:13.5px;line-height:1.5}" +
    ".lgt *{box-sizing:border-box}.lgt .tete{padding:18px 20px 0;display:flex;flex-direction:column;gap:12px}.lgt .corps{padding:16px 20px 24px;overflow:auto;display:flex;flex-direction:column;gap:14px;flex:1}.lgt h2{margin:0;font:650 19px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}" +
    ".lgt .onglets{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto}.lgt .onglets button{border:0;background:transparent;padding:9px 12px;font:600 13px 'Inter',sans-serif;color:var(--txt-soft);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}.lgt .onglets button.on{color:var(--accent);border-bottom-color:var(--accent)}" +
    ".lgt .pied{padding:12px 20px calc(12px + env(safe-area-inset-bottom,0px));border-top:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap}.lgt .carte{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}" +
    ".lgt .lib{font:600 10.5px 'Inter',sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--txt-faint)}.lgt .note{font-size:12.5px;color:var(--txt-soft)}.lgt .mono{font-family:ui-monospace,Menlo,monospace}.lgt .reglage{display:flex;gap:14px;align-items:center}.lgt .reglage .sp{flex:1}" +
    ".lgt .sw{position:relative;width:38px;height:22px;flex:none;border-radius:999px;border:0;background:var(--line-strong,var(--line));cursor:pointer;padding:0}.lgt .sw::after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .15s}.lgt .sw.on{background:var(--accent)}.lgt .sw.on::after{transform:translateX(16px)}" +
    "@media(max-width:860px){.lgt{top:auto;height:88vh;width:100%;border-left:0;border-top:1px solid var(--line-strong,var(--line));border-radius:20px 20px 0 0}.lg .demande{flex-direction:column}.lg .demande .btn{width:100%}.lg .g2,.lg .grille{grid-template-columns:minmax(0,1fr)}}" +
    "@media (prefers-reduced-motion:reduce){.lg *,.lgt *{transition:none!important}}";

  const S = { gere: true, cat: [], sections: [], act: { actes: [], verrous: [], autonomie: "reine", fenetre: "nuit", gel: false }, constats: null, rep: new Set(), q: "", fam: "toutes", etat: "tous", imp: "toutes", vue: "grille", ouvert: "", onglet: "apercu", occupe: false };
  let racine = null, corpsEl = null, sec = "vue", hooks = {}, escLie = false;
  const lire = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } };
  const ecrire = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  const avance = () => lire("lg.avance", "0") === "1";

  const depuis = (ts) => { const s = Math.max(0, Date.now() / 1000 - ts); if (s < 90) return "à l’instant"; if (s < 3600) return "il y a " + Math.round(s / 60) + " min"; if (s < 86400) return "il y a " + Math.round(s / 3600) + " h"; return new Date(ts * 1000).toLocaleDateString("fr-FR"); };
  const qui = (par) => { const p = String(par || ""); if (["cassandra", "itare"].includes(p)) return p.charAt(0).toUpperCase() + p.slice(1); if (p === "agent") return "Un agent"; if (p === "noyau") return "Le noyau"; if (!p || p === "utilisateur" || p === "humain") return "Un utilisateur"; return p.split("@")[0]; };
  const nomDe = (id) => { const m = S.cat.find((x) => x.id === id); return m ? m.nom : id; };
  const pill = (t, c, i) => '<span class="p ' + (c || "") + '">' + (i ? ic(i) : "") + esc(t) + "</span>";
  const niveauMod = (m) => (m.etat === "refuse" ? pill("Refusé", "dg", "warn") : m.confiance === "interne" ? pill("Noyau", "ok", "shield") : m.confiance === "local" ? pill("Clé de l’administrateur", "") : pill("Installé", ""));
  const sectionDe = (id) => S.sections.find((s) => s.id === id) || { id: id, libelle: id, icone: "" };
  const famIcone = (id) => ((CASS.modulesUi && CASS.modulesUi.famIcone && CASS.modulesUi.famIcone(id)) || "box");
  const iconeMod = (m) => (CASS.modulesUi && CASS.modulesUi.trace && m.icone_trace && CASS.modulesUi.trace(m.icone_trace)) ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + CASS.modulesUi.trace(m.icone_trace) + "</svg>" : ic("box");

  async function charger() {
    const [l, a] = await Promise.all([agir("modules.lister"), agir("modules.activite", { limite: 60 }).catch(() => null)]);
    S.cat = l.modules || [];
    S.gere = l.gere !== false;
    if (!S.gere) S.cat.forEach((m) => { if (m.etat !== "refuse") m.etat = "actif"; });           // instance de développement : tout ce qui est chargé tourne
    S.sections = l.sections || [];
    if (a) S.act = a;
    else S.act = Object.assign({}, S.act, { autonomie: l.autonomie || S.act.autonomie });
  }
  async function chargerConstats() {
    if (S.constats !== null) return;
    S.constats = { chargement: true, liste: [] };
    try { const r = await agir("modules.entretien", { simuler: true }); S.constats = { chargement: false, liste: r.constats || [], erreurs: r.erreurs || [] }; }
    catch (e) { S.constats = { chargement: false, liste: [], erreurs: [e.message || String(e)] }; }
    if (sec === "vue") dessiner();
  }

  const titre = (t, d, act) => '<div class="barre"><div class="titre" style="flex:1 1 260px;min-width:0"><h1>' + esc(t) + "</h1><p>" + esc(d) + "</p></div>" + (act || "") + "</div>";
  const banDev = () => S.gere ? "" : '<div class="alerte in" role="status"><div class="sp"><b>Instance de développement.</b> <span class="note">Tous les modules sont chargés : activer ou désactiver ne change rien ici, et Cassandra n’a rien à entretenir.</span></div></div>';
  const banAvance = () => avance() ? '<div class="alerte al avance" role="status"><div class="ico sm al">' + ic("warn") + '</div><div class="sp"><b>Mode avancé.</b> <span class="note">Tu as les vrais boutons (interrupteurs, retrait). Cassandra voit tout ce que tu fais, et chaque geste se défait.</span></div><button class="btn mini" data-a="avance">Quitter</button></div>' : "";

  // ── la Vue d'ensemble ───────────────────────────────────────────────
  function recitLi(a, i) {
    const dep = a.detail && /^mise à jour/.test(a.detail), verbe = a.geste === "installe" && dep ? "a mis à jour" : (GESTES[a.geste] || a.geste);
    return '<div class="li"><div class="ico sm">' + ic("check") + '</div><div class="sp"><b>' + esc(qui(a.par)) + "</b> " + esc(verbe) + " <b>" + esc(nomDe(a.module)) + "</b>" + (a.detail ? '<span class="note">' + esc(a.detail) + "</span>" : "") +
      (a.pourquoi ? '<span class="pourquoi">' + ic("eye") + esc(a.pourquoi) + "</span>" : "") + '<span class="faint" style="font-size:11.5px">' + esc(depuis(a.ts)) + "</span></div>" +
      (a.defaire ? '<button class="btn mini" data-a="defaire" data-i="' + i + '">Défaire</button>' : "") + "</div>";
  }
  function vue() {
    const A = S.act, actifs = S.cat.filter((m) => m.etat === "actif").length, n = S.cat.length;
    const gel = !!A.gel, laisses = S.constats && S.constats.liste || [];
    const hero = '<div class="carte hero"><div class="l1"><div class="ico" style="width:46px;height:46px;border-radius:14px">' + ic(gel ? "warn" : "bot") + '</div><div style="flex:1;min-width:240px"><h2>' + (gel ? "Cassandra est en pause" : "Tout va bien") + '</h2><p class="note" style="margin-top:3px;max-width:62ch">' +
      (gel ? "Elle observe et raconte, elle n’agit plus. Reprends quand tu veux." : "Cassandra s’occupe des modules" + (A.actes && A.actes[0] ? " : dernier geste " + esc(depuis(A.actes[0].ts)) + "." : " : rien à signaler pour l’instant.")) + "</p></div>" +
      '<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" data-a="passe"' + (S.occupe ? " disabled" : "") + '>Lancer une passe</button><button class="btn' + (gel ? " pri" : "") + '" data-a="gel">' + (gel ? "Reprendre" : "Mettre en pause") + "</button></div></div>" +
      '<div class="demande"><input id="lg-dem" placeholder="Demander à Cassandra : « installe Sentinelle du disque », « qu’est-ce qui ne va pas ? »…" aria-label="Demander à Cassandra"><button class="btn pri" data-a="demande">Demander</button></div>' +
      '<div class="chips"><button class="chip" data-sug="Qu’est-ce qui ne va pas ?">Qu’est-ce qui ne va pas ?</button><button class="chip" data-sug="Qu’est-ce qui consomme le plus ?">Qu’est-ce qui consomme le plus ?</button><button class="chip" data-sug="Mets tout à jour">Mets tout à jour</button></div></div>';
    const stats = '<div class="stats"><div class="stat ok"><b>' + actifs + "/" + n + '</b><span>modules actifs</span></div><div class="stat"><b>' + S.cat.filter((m) => m.etat === "inactif").length + '</b><span>inactifs</span></div><div class="stat"><b>' + (A.verrous || []).length + "</b><span>verrouillés</span></div></div>";
    const recit = '<div class="carte"><div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><h3>Ce que Cassandra a fait</h3><span class="note">Chaque ligne se défait en un clic. Rien n’est effacé pour de bon : un module retiré reste 30 jours en corbeille.</span></div><div class="liste">' +
      ((A.actes || []).length ? A.actes.slice(0, 5).map(recitLi).join("") : '<div class="vide">Rien pour l’instant. Ce que Cassandra fait ou laisse de côté apparaîtra ici.</div>') + "</div></div>";
    const niveaux = '<div class="carte"><h3>Jusqu’où Cassandra va seule</h3><div style="display:flex;flex-direction:column;gap:8px">' + Object.entries(NIV).map(([k, v]) =>
      '<button class="radio' + (A.autonomie === k ? " on" : "") + '" data-a="autonomie" data-k="' + k + '" role="radio" aria-checked="' + (A.autonomie === k) + '"><i></i><div><b>' + v[0] + (k === "reine" ? ' <span class="p ok">défaut</span>' : "") + '</b><span class="note" style="display:block">' + v[1] + "</span></div></button>").join("") +
      '</div><p class="note">À tout niveau : elle n’installe que le registre officiel et les éditeurs vérifiés, jamais un module révoqué, jamais un module vital désactivé, jamais un module verrouillé. Ce niveau est un plafond ; l’autonomie qu’elle gagne par les preuves se suit dans Évolution.</p></div>';
    const cote = '<div class="carte"><h3>Ce que je n’ai pas fait seule, et pourquoi</h3>' + (!S.constats || S.constats.chargement ? '<p class="note">Je regarde le registre…</p>' :
      laisses.length ? '<div class="liste">' + laisses.map((c) => '<div class="li"><div class="sp"><span class="note" style="display:block;color:var(--txt)">' + esc(c) + "</span></div></div>").join("") + "</div>" : '<p class="note">Rien : tout ce que ma règle permet est fait.</p>') +
      '<p class="note">Ce n’est pas une file d’attente : je continue sans ton accord. Cette liste dit seulement ce que ma règle m’a fait laisser de côté.</p></div>';
    return titre("Vue d’ensemble", "Les modules de cette instance : Cassandra s’en occupe, tu vois ce qu’elle fait.") + banDev() + banAvance() + hero + stats + recit + '<div class="g2">' + niveaux + cote + "</div>";
  }

  // ── Installés ───────────────────────────────────────────────────────
  const filtres = () => S.cat.filter((m) => (S.fam === "toutes" || (m.famille || "autres") === S.fam) && (S.etat === "tous" || (S.etat === "actif" && m.etat === "actif") || (S.etat === "inactif" && m.etat !== "actif") || (S.etat === "verrou" && m.verrou)) &&
    (S.imp === "toutes" || m.importance === S.imp) && (!S.q || (m.nom + " " + m.id + " " + (m.description || "")).toLowerCase().indexOf(S.q.toLowerCase()) >= 0));
  function carteMod(m) {
    const on = m.etat === "actif", av = avance();
    const sw = av ? '<button class="sw' + (on ? " on" : "") + '" data-a="bascule" data-id="' + esc(m.id) + '"' + (m.importance === "vital" || m.etat === "refuse" || !S.gere ? " disabled" : "") + ' aria-label="Activer ' + esc(m.nom) + '" role="switch" aria-checked="' + on + '"></button>' : pill(on ? "actif" : m.etat === "a_installer" ? "à installer" : "inactif", on ? "ok" : "");
    return '<div class="carte mod' + (on ? "" : " off") + '" data-ouvrir="' + esc(m.id) + '" role="button" tabindex="0"><div class="l1"><div class="ico' + (on ? "" : " off") + '">' + iconeMod(m) + '</div><div class="sp"><h3>' + esc(m.nom) + '</h3><div class="mono note">' + esc(m.id) + " · v" + esc(m.version) + "</div></div>" + sw + "</div>" +
      '<div class="desc">' + esc(m.description) + '</div><div class="pied">' + niveauMod(m) + (IMP[m.importance] ? '<span class="faint" style="font:600 11px Inter,sans-serif">' + IMP[m.importance][0] + "</span>" : "") + (m.verrou ? pill("verrouillé", "", "lock") : "") + "</div></div>";
  }
  function inst() {
    const l = filtres(), n = (f) => S.cat.filter(f).length, sects = S.sections.filter((s) => S.cat.some((m) => (m.famille || "autres") === s.id));
    const filtre = S.fam !== "toutes" || S.imp !== "toutes" || S.etat !== "tous" || S.q;
    const bloc = sects.filter((s) => l.some((m) => (m.famille || "autres") === s.id)).map((s) => {
      const g = l.filter((m) => (m.famille || "autres") === s.id), ouv = !S.rep.has(s.id);
      return '<section class="rub"><button class="rub-t" data-a="rep" data-id="' + esc(s.id) + '" aria-expanded="' + ouv + '"><span class="ico sm">' + ic(famIcone(s.id)) + "</span><h3>" + esc(s.libelle) + '</h3><span class="p">' + g.length + '</span><span class="note">' + g.filter((m) => m.etat === "actif").length + ' actif(s)</span><svg class="chev' + (ouv ? "" : " ferme") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + I.chev + "</svg></button>" +
        (ouv ? '<div class="grille">' + g.map(carteMod).join("") + "</div>" : "") + "</section>";
    }).join("");
    return titre("Installés", "Tout ce qui tourne sur cette instance, avec ce qui s’arrête si on le coupe.", '<button class="btn' + (avance() ? " pri" : "") + '" data-a="avance" title="Affiche les interrupteurs. Cassandra sait tout ce que tu fais.">Mode avancé : ' + (avance() ? "oui" : "non") + "</button>") + banDev() + banAvance() +
      '<div class="barre"><input type="search" id="lg-q" placeholder="Rechercher parmi les modules installés…" value="' + esc(S.q) + '" aria-label="Rechercher un module"><select class="sel" data-sel="fam" aria-label="Section"><option value="toutes">Toutes les sections</option>' +
      S.sections.filter((s) => S.cat.some((m) => (m.famille || "autres") === s.id)).map((s) => '<option value="' + esc(s.id) + '"' + (S.fam === s.id ? " selected" : "") + ">" + esc(s.libelle) + "</option>").join("") + '</select><select class="sel" data-sel="imp" aria-label="Importance">' +
      [["toutes", "Toutes les importances"], ["vital", "Vital"], ["important", "Important"], ["optionnel", "Optionnel"]].map((c) => '<option value="' + c[0] + '"' + (S.imp === c[0] ? " selected" : "") + ">" + c[1] + "</option>").join("") + "</select>" + (filtre ? '<button class="btn mini" data-a="reset">Réinitialiser</button>' : "") + "</div>" +
      '<div class="seg">' + [["tous", "Tous", S.cat.length], ["actif", "Actifs", n((m) => m.etat === "actif")], ["inactif", "Inactifs", n((m) => m.etat !== "actif")], ["verrou", "Verrouillés", n((m) => m.verrou)]].map((c) => '<button class="' + (S.etat === c[0] ? "on" : "") + '" data-etat="' + c[0] + '">' + c[1] + ' <span class="cnt">' + c[2] + "</span></button>").join("") + "</div>" +
      (bloc || '<div class="carte vide">Aucun module ne correspond.</div>');
  }

  // ── les sections pas encore portées : on renvoie vers ce qui existe ───────
  function ailleurs(libelle) {
    return titre(libelle, "Cette section arrive.") + '<div class="carte pret"><h3>En attendant</h3><p class="note">La gestion complète reste disponible dans le menu de l’avatar : « Modules et Applications » (états, réglages, dépendances) et « App Store » (registre, archives, versions).</p><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" data-a="ouvrir-modules">Modules et Applications</button><button class="btn" data-go="shop">Ouvrir la boutique</button></div></div>';
  }

  // ── le tiroir d'un module ───────────────────────────────────────────
  function fermerTiroir() { ["lg-tiroir", "lg-voile"].forEach((i) => { const e = document.getElementById(i); if (e) e.remove(); }); S.ouvert = ""; }
  function ouvrir(id, onglet) {
    const m = S.cat.find((x) => x.id === id); if (!m) return;
    S.ouvert = id; S.onglet = onglet || "apercu";
    fermerTiroir(); S.ouvert = id;
    const v = document.createElement("div"); v.className = "lgv"; v.id = "lg-voile"; v.addEventListener("click", fermerTiroir);
    const t = document.createElement("aside"); t.className = "lgt"; t.id = "lg-tiroir"; t.setAttribute("role", "dialog"); t.setAttribute("aria-modal", "true"); t.setAttribute("aria-label", "Détail du module " + m.nom);
    document.body.appendChild(v); document.body.appendChild(t);
    t.addEventListener("click", (e) => { const b = e.target.closest("[data-t]"); if (b) gesteTiroir(b, m); });
    dessinerTiroir(m, null);
    const f = t.querySelector("[data-t=fermer]"); if (f) f.focus();
    if (S.onglet === "sante" || S.onglet === "versions") chargerOnglet(m);
  }
  async function chargerOnglet(m) {
    let r = null; try { r = S.onglet === "sante" ? await agir("modules.sante", { module: m.id }) : await agir("modules.versions", { module: m.id }); } catch (e) { r = { erreur: e.message || String(e) }; }
    if (S.ouvert === m.id) dessinerTiroir(m, r);
  }
  function dessinerTiroir(m, extra) {
    const t = document.getElementById("lg-tiroir"); if (!t) return;
    const on = m.etat === "actif", av = avance(), reque = (m.requis_par || []).map(nomDe);
    const ONG = [["apercu", "Aperçu"], ["dep", "Dépendances"], ["perm", "Permissions"], ["sante", "Santé"], ["versions", "Versions"]];
    const p = m.permissions || {};
    const corps = {
      apercu: '<div class="carte"><div class="lib">Sans lui</div><p><b>' + esc(m.sans || "Non déclaré.") + "</b></p>" + (reque.length ? '<p class="note">Cela touche aussi : ' + reque.map(esc).join(", ") + ".</p>" : "") + "</div>" +
        '<div class="carte"><div class="reglage"><div class="sp"><b>Cassandra n’y touche pas</b><span class="note" style="display:block">Verrou : ni mise à jour, ni pause, ni retrait par elle. Utile pour un module que tu règles à la main.</span></div><button class="sw' + (m.verrou ? " on" : "") + '" data-t="verrou" aria-label="Verrouiller ' + esc(m.nom) + '" role="switch" aria-checked="' + !!m.verrou + '"' + (m.importance === "vital" ? " disabled" : "") + "></button></div></div>" +
        '<div class="carte"><div class="lib">Famille</div><div>' + esc(sectionDe(m.famille || "autres").libelle) + '</div><div class="lib">Auteur</div><div>' + esc(m.auteur || "—") + '</div><div class="lib">Licence</div><div>' + esc(m.licence || "—") + "</div></div>",
      dep: '<div class="carte"><div class="lib">Il a besoin de</div><div>' + ((m.requiert || []).map((x) => '<span class="p">' + esc(x) + "</span>").join(" ") || '<span class="note">rien</span>') + '</div><div class="lib">Ont besoin de lui</div><div>' + ((m.requis_par || []).map((x) => '<span class="p">' + esc(x) + "</span>").join(" ") || '<span class="note">personne</span>') + "</div></div>",
      perm: '<div class="carte"><div class="lib">Ce qu’il demande</div><div class="note">Réseau : ' + esc((p.reseau || []).join(", ") || "aucun") + "</div><div class=\"note\">Écritures : " + esc((p.ecritures || []).join(", ") || "aucune") + "</div><div class=\"note\">Privilèges : " + esc((p.privileges || []).join(", ") || "aucun") + "</div></div><p class=\"note\">Déclaratives : le module tourne dans Cassandra. Elles servent à décider, pas encore à contenir.</p>",
      sante: extra ? (extra.erreur ? '<div class="alerte dg"><div class="sp">' + esc(extra.erreur) + "</div></div>" : '<div class="carte"><div class="lib">Verdict</div><div>' + pill({ sain: "sain", a_surveiller: "à surveiller", en_echec: "en échec" }[extra.verdict] || extra.verdict || "—", extra.verdict === "sain" ? "ok" : extra.verdict === "en_echec" ? "dg" : "al") + '</div><div class="lib">Constats ouverts</div><div>' + esc(extra.constats_ouverts == null ? "—" : extra.constats_ouverts) + "</div></div>") : '<p class="note">Lecture…</p>',
      versions: extra ? (extra.erreur ? '<div class="alerte dg"><div class="sp">' + esc(extra.erreur) + "</div></div>" : '<div class="carte"><div class="lib">Versions restaurables</div>' + ((extra.sauvegardes || []).length ? extra.sauvegardes.map((s) => '<div class="note mono">' + esc(s.version) + " · " + esc(s.raison) + " · " + esc(depuis(s.ts)) + "</div>").join("") : '<p class="note">Aucune : ce module est livré avec le noyau, ou jamais remplacé.</p>') + "</div>") : '<p class="note">Lecture…</p>',
    }[S.onglet];
    t.innerHTML = '<div class="tete"><div style="display:flex;gap:12px;align-items:center"><div class="ico">' + iconeMod(m) + '</div><div style="flex:1;min-width:0"><h2>' + esc(m.nom) + '</h2><div class="mono note">' + esc(m.id) + " · v" + esc(m.version) + '</div></div><button class="btn mini" data-t="fermer">Fermer</button></div><div style="display:flex;gap:6px;flex-wrap:wrap">' +
      niveauMod(m) + pill((IMP[m.importance] || ["—"])[0], (IMP[m.importance] || [])[1]) + pill(on ? "actif" : "inactif", on ? "ok" : "") + '</div><div class="onglets" role="tablist">' + ONG.map((o) => '<button role="tab" class="' + (S.onglet === o[0] ? "on" : "") + '" data-t="onglet" data-o="' + o[0] + '">' + o[1] + "</button>").join("") + '</div></div><div class="corps">' + corps + "</div>" +
      '<div class="pied">' + (m.importance === "vital" ? '<span class="note">Vital : ne se désactive ni ne se désinstalle.</span>' : av ? '<button class="btn" data-t="bascule">' + (on ? "Désactiver" : "Activer") + "</button>" : '<button class="btn pri" data-t="demander">Demander à Cassandra de le ' + (on ? "désactiver" : "activer") + '</button><span class="note">Les boutons directs sont dans le « Mode avancé ».</span>') + "</div>";
  }
  async function gesteTiroir(b, m) {
    const g = b.dataset.t;
    if (g === "fermer") return fermerTiroir();
    if (g === "onglet") { S.onglet = b.dataset.o; dessinerTiroir(m, null); if (S.onglet === "sante" || S.onglet === "versions") chargerOnglet(m); return; }
    if (g === "demander") { fermerTiroir(); return demander((m.etat === "actif" ? "Désactive " : "Active ") + m.nom); }
    try {
      if (g === "verrou") { await agir("modules.verrouiller", { module: m.id, verrou: !m.verrou }); dire(m.verrou ? m.nom + " : Cassandra peut de nouveau s’en occuper." : m.nom + " : Cassandra n’y touchera plus.", "ok"); }
      else if (g === "bascule") { await agir(m.etat === "actif" ? "modules.desactiver" : "modules.activer", { module: m.id }); dire(m.nom + (m.etat === "actif" ? " désactivé." : " activé."), "ok"); }
      await rafraichir(); const n = S.cat.find((x) => x.id === m.id); if (n) dessinerTiroir(n, null);
    } catch (e) { dire(e.message || String(e), "err"); }
  }

  // ── les gestes de la page ────────────────────────────────────────────
  function demander(texte) {
    if (CASS.disposition && CASS.disposition.demander) CASS.disposition.demander(texte);
    else dire("L’assistant n’est pas disponible sur cet écran.", "err");
  }
  async function rafraichir() { await charger(); dessiner(); }
  async function geste(b) {
    const a = b.dataset.a;
    try {
      if (a === "avance") { ecrire("lg.avance", avance() ? "0" : "1"); dessiner(); return; }
      if (a === "rep") { S.rep.has(b.dataset.id) ? S.rep.delete(b.dataset.id) : S.rep.add(b.dataset.id); dessiner(); return; }
      if (a === "reset") { S.fam = "toutes"; S.imp = "toutes"; S.etat = "tous"; S.q = ""; dessiner(); return; }
      if (a === "demande") { const d = racine.querySelector("#lg-dem"), v = d ? d.value.trim() : ""; if (d) d.value = ""; if (v) demander(v); else dire("Dis-lui ce que tu veux.", ""); return; }
      if (a === "ouvrir-modules") { if (hooks.ouvrirModules) hooks.ouvrirModules(); return; }
      if (a === "gel") { await agir("urgence.geler", { actif: !S.act.gel }); dire(S.act.gel ? "Cassandra reprend." : "Cassandra est en pause : elle observe, elle n’agit plus.", "ok"); await rafraichir(); return; }
      if (a === "passe") { S.occupe = true; dessiner(); const r = await agir("modules.entretien", { forcer: true }); S.occupe = false; S.constats = null; dire((r.actions || []).length ? (r.actions.length + " geste(s) fait(s).") : "Passe faite : rien à faire pour l’instant.", "ok"); await rafraichir(); return; }
      if (a === "autonomie") { await agir("reglages.regler", { cle: "modules.autonomie", valeur: b.dataset.k }); dire("Autonomie : " + NIV[b.dataset.k][0] + ".", "ok"); S.constats = null; await rafraichir(); return; }
      if (a === "defaire") { const l = S.act.actes[+b.dataset.i]; if (!l) return; await agir("modules.annuler", { module: l.module, geste: l.geste }); dire("C’est défait. Cassandra en prend note.", "ok"); await rafraichir(); return; }
      if (a === "bascule") { const m = S.cat.find((x) => x.id === b.dataset.id); if (!m) return; await agir(m.etat === "actif" ? "modules.desactiver" : "modules.activer", { module: m.id }); await rafraichir(); return; }
    } catch (e) { S.occupe = false; dire(e.message || String(e), "err"); dessiner(); }
  }

  // ── le montage ──────────────────────────────────────────────────────
  function dessiner() {
    if (!racine) return;
    const focus = document.activeElement && document.activeElement.id;
    let h;
    if (sec === "vue") h = vue();
    else if (sec === "inst") h = inst();
    else if (sec === "shop") h = '<div id="lg-boutique"></div>';
    else h = ailleurs((SECTIONS.find((x) => x[0] === sec) || [0, "Logithèque"])[1]);
    racine.innerHTML = h;
    if (sec === "shop" && CASS.pageAppStore) { const z = racine.querySelector("#lg-boutique"); CASS.pageAppStore(z); }
    if (focus === "lg-q") { const q = racine.querySelector("#lg-q"); if (q) { q.focus(); q.setSelectionRange(99, 99); } }
    if (sec === "vue") chargerConstats();
  }
  CASS.logitheque = { sections: SECTIONS, pretes: PRETES };
  CASS.pageLogitheque = async function (corps, section, h) {
    hooks = h || {}; sec = SECTIONS.some((x) => x[0] === section) ? section : "vue";
    const anc = document.getElementById("lg-css"); if (anc) anc.remove();
    const st = document.createElement("style"); st.id = "lg-css"; st.textContent = CSS; document.head.appendChild(st);
    fermerTiroir();
    corps.innerHTML = ""; racine = document.createElement("div"); racine.className = "lg"; corps.appendChild(racine); corpsEl = corps;
    racine.innerHTML = '<div class="carte vide">Lecture des modules…</div>';
    racine.addEventListener("click", (e) => {
      const go = e.target.closest("[data-go]"); if (go) { if (hooks.aller) hooks.aller(go.dataset.go); return; }
      const sug = e.target.closest("[data-sug]"); if (sug) { demander(sug.dataset.sug); return; }
      const et = e.target.closest("[data-etat]"); if (et) { S.etat = et.dataset.etat; dessiner(); return; }
      const b = e.target.closest("[data-a]"); if (b) { e.stopPropagation(); geste(b); return; }
      const m = e.target.closest("[data-ouvrir]"); if (m) ouvrir(m.dataset.ouvrir);
    });
    racine.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-ouvrir]")) { e.preventDefault(); ouvrir(e.target.dataset.ouvrir); } if (e.key === "Enter" && e.target.id === "lg-dem") { e.preventDefault(); const v = e.target.value.trim(); e.target.value = ""; if (v) demander(v); } });
    racine.addEventListener("input", (e) => { if (e.target.id === "lg-q") { S.q = e.target.value; dessiner(); } });
    racine.addEventListener("change", (e) => { const k = e.target.dataset && e.target.dataset.sel; if (k) { S[k] = e.target.value; dessiner(); } });
    if (!escLie) { escLie = true; document.addEventListener("keydown", (e) => { if (e.key === "Escape" && document.getElementById("lg-tiroir")) fermerTiroir(); }); }
    try { await charger(); } catch (e) { racine.innerHTML = '<div class="carte vide">Les modules ne se lisent pas : ' + esc(e.message || e) + "</div>"; return; }
    dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
