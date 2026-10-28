// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : Écran Utilisateurs et groupes
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.2.0  #e2fc4a
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : Les pages « Utilisateurs et groupes » : listes, fiches, droits par utilisateur et par groupe, matrice, « qui peut… ? », journal.
// MÉTHODE    : une seule scène (CASS.sceneSurMesure.comptes) ; la page vient de l'écran ouvert (u_liste, u_nouveau, g_liste, g_nouveau, matrice, qui, journal) et la navigation interne ne change que l'état.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.2.0 empreinte=e2fc4a ▼▼▼
// Les données viennent des capacités comptes.* (lister, creer, modifier, desactiver, reactiver, creer_jeton, regles_mdp, moi) et droits.* (etat, catalogue, decisions, appliquer, groupe, membre, qui_peut, voir_comme, journal).
// Un droit se règle en trois états (hérité, accordé, refusé) ; la décision et son pourquoi viennent du moteur (droits.decisions), jamais recalculés ici.
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const PAGES = { vue_utilisateurs: "u_liste", u_liste: "u_liste", u_nouveau: "u_nouveau", g_liste: "g_liste", g_nouveau: "g_nouveau", matrice: "matrice", qui: "qui", journal: "journal" };
  const ETATS = [["herite", "Hérité"], ["accorde", "Accordé"], ["refuse", "Refusé"]];
  const BOUCLIER = '<svg class="cu-i sens" viewBox="0 0 24 24"><title>Droit sensible : chaque usage est journalisé</title><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/></svg>';
  const CSS = ".sh-scene:has(>.sh-corps>.cu){width:100%}.cu{display:grid;gap:14px;color:var(--txt);font:13.5px/1.45 'Inter',system-ui,sans-serif}.cu *{box-sizing:border-box}.cu button{font:inherit;color:inherit;cursor:pointer}" +
    ".cu .cu-i{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;flex:none}.cu .sens{color:var(--warn)}" +
    ".cu .cu-fil{font-size:12px;color:var(--txt-faint)}.cu .cu-fil b{color:var(--txt-soft);font-weight:600}.cu .cu-fil button{border:0;background:none;color:var(--accent);padding:0;font-weight:600}" +
    ".cu h1{margin:0;font:650 22px 'Inter',sans-serif;color:var(--txt-strong,var(--txt))}.cu .cu-lead{margin:2px 0 0;color:var(--txt-soft);max-width:70ch}" +
    ".cu .cu-carte{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px}.cu .cu-carte h3{margin:0 0 10px;font-size:14px;display:flex;gap:8px;align-items:center}" +
    ".cu .cu-barre{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.cu .cu-grow{flex:1;min-width:140px}" +
    ".cu .cu-btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));border-radius:10px;padding:6px 12px;font-weight:600;font-size:13px;display:inline-flex;gap:6px;align-items:center}.cu .cu-btn:hover{border-color:var(--accent)}" +
    ".cu .cu-btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.cu .cu-btn.dng{color:var(--danger)}.cu .cu-btn.sm{padding:3px 9px;font-size:12px}.cu .cu-btn[disabled]{opacity:.45;pointer-events:none}" +
    ".cu input[type=text],.cu input[type=email],.cu input[type=password],.cu input[type=search],.cu select{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:7px 10px;width:100%;min-width:0}" +
    ".cu .cu-f{display:block;font:600 10.5px 'JetBrains Mono',monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint);margin:0 0 4px}.cu .cu-g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}" +
    ".cu .cu-chip{display:inline-flex;gap:5px;align-items:center;font-size:11.5px;font-weight:600;border-radius:999px;padding:2px 9px;background:var(--surface);color:var(--txt-soft);border:1px solid var(--line);white-space:nowrap}" +
    ".cu .cu-chip.ok{background:color-mix(in srgb,var(--ok) 13%,transparent);color:var(--ok);border-color:transparent}.cu .cu-chip.warn{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn);border-color:transparent}" +
    ".cu .cu-chip.dng{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger);border-color:transparent}.cu .cu-chip.acc{background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent);border-color:transparent}.cu .cu-chip.info{background:color-mix(in srgb,var(--info,var(--accent)) 12%,transparent);color:var(--info,var(--accent));border-color:transparent}" +
    ".cu .cu-av{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font:600 12px 'JetBrains Mono',monospace;background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent);flex:none}.cu .cu-av.big{width:60px;height:60px;font-size:19px}" +
    ".cu .cu-tw{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface)}.cu table{border-collapse:collapse;width:100%;font-size:13px}.cu th{font:600 10.5px 'JetBrains Mono',monospace;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);text-align:left;padding:9px 12px;white-space:nowrap}" +
    ".cu td{padding:9px 12px;border-top:1px solid var(--line);vertical-align:middle}.cu tr.cu-l{cursor:pointer}.cu tr.cu-l:hover td{background:color-mix(in srgb,var(--accent) 8%,transparent)}" +
    ".cu .cu-who{display:flex;gap:10px;align-items:center;min-width:0}.cu .cu-who b{display:block}.cu .cu-who small,.cu .cu-why{color:var(--txt-faint);font-size:11.8px}" +
    ".cu .cu-tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);overflow-x:auto}.cu .cu-tab{border:0;background:none;padding:8px 13px;color:var(--txt-soft);font-weight:500;border-bottom:2px solid transparent;white-space:nowrap}.cu .cu-tab.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}" +
    ".cu .cu-split{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:14px;align-items:start}.cu .cu-split>*{min-width:0}.cu .cu-hero{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.cu .cu-hero .cu-m{flex:1;min-width:200px}.cu .cu-hero h2{margin:0;font-size:19px}" +
    ".cu .cu-kpis{display:flex;gap:8px;flex-wrap:wrap}.cu .cu-kpi{flex:1;min-width:100px;border:1px solid var(--line);border-radius:12px;padding:8px 12px;background:var(--surface)}.cu .cu-kpi b{font:600 19px 'JetBrains Mono',monospace;display:block}.cu .cu-kpi span{font-size:11.5px;color:var(--txt-faint)}.cu .cu-kpi.ok b{color:var(--ok)}.cu .cu-kpi.dng b{color:var(--danger)}.cu .cu-kpi.warn b{color:var(--warn)}" +
    ".cu .cu-seg{display:inline-flex;border:1px solid var(--line-strong,var(--line));border-radius:10px;overflow:hidden;background:var(--surface-solid,var(--surface));flex:none}.cu .cu-seg button{border:0;background:none;padding:4px 9px;font-size:12px;font-weight:500;color:var(--txt-soft);border-left:1px solid var(--line)}.cu .cu-seg button:first-child{border-left:0}" +
    ".cu .cu-seg button.on{font-weight:600;color:var(--txt)}.cu .cu-seg button.on[data-v=accorde]{background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok)}.cu .cu-seg button.on[data-v=refuse]{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger)}.cu .cu-seg button.on[data-v=herite]{background:color-mix(in srgb,var(--accent) 10%,transparent);color:var(--accent)}.cu .cu-seg.lock{opacity:.45;pointer-events:none}" +
    ".cu .cu-fl{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));border-radius:999px;padding:3px 11px;font-size:12px;font-weight:500}.cu .cu-fl.on{background:var(--accent);color:var(--on-accent,#fff);border-color:var(--accent)}.cu .cu-fls{display:flex;gap:6px;flex-wrap:wrap}" +
    ".cu .cu-mod{border:1px solid var(--line);border-radius:12px;background:var(--surface);overflow:hidden}.cu .cu-mod+.cu-mod{margin-top:8px}.cu .cu-mh{display:flex;gap:10px;align-items:center;padding:9px 12px;cursor:pointer;flex-wrap:wrap}.cu .cu-mh .nm{display:flex;gap:8px;align-items:center;font-weight:600;min-width:160px}.cu .cu-mh .car{transition:transform .15s}.cu .cu-mod.open .car{transform:rotate(90deg)}" +
    ".cu .cu-mh .cnt{font:600 11px 'JetBrains Mono',monospace;color:var(--txt-faint)}.cu .cu-mh .act{margin-left:auto;display:flex;gap:4px}.cu .cu-bulk{border:0;background:none;color:var(--accent);font-size:12px;font-weight:600;padding:3px 6px;border-radius:6px}.cu .cu-bulk:hover{background:color-mix(in srgb,var(--accent) 10%,transparent)}.cu .cu-rights{display:none;border-top:1px solid var(--line)}.cu .cu-mod.open .cu-rights{display:block}" +
    ".cu .cu-rt{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:12px;align-items:center;padding:8px 12px;border-top:1px solid var(--line)}.cu .cu-rt:first-child{border-top:0}.cu .cu-rt.chg{background:color-mix(in srgb,var(--warn) 10%,transparent)}.cu .cu-rt .eff{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}" +
    ".cu .cu-bar{position:sticky;bottom:10px;display:none;gap:12px;align-items:center;flex-wrap:wrap;background:var(--txt);color:var(--bg);border-radius:14px;padding:9px 14px;box-shadow:var(--shadow-glass,0 8px 30px rgba(0,0,0,.3));z-index:5}.cu .cu-bar.on{display:flex}.cu .cu-bar .cu-btn{color:var(--txt)}.cu .cu-bar label{display:flex;gap:6px;align-items:center;font-size:12.5px}" +
    ".cu .cu-adm{display:flex;gap:12px;align-items:center;justify-content:space-between;border:1px dashed var(--warn);background:color-mix(in srgb,var(--warn) 10%,transparent);border-radius:12px;padding:10px 12px;flex-wrap:wrap}.cu .cu-sw{position:relative;width:38px;height:22px;border-radius:99px;background:var(--line-strong,var(--line));border:0;flex:none}.cu .cu-sw:after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:left .15s}.cu .cu-sw.on{background:var(--accent)}.cu .cu-sw.on:after{left:19px}" +
    ".cu .cu-lst{list-style:none;margin:0;padding:0;display:grid;gap:8px}.cu .cu-lst li{display:flex;gap:8px;align-items:center}.cu .cu-tl{list-style:none;margin:0;padding:0}.cu .cu-tl li{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line)}.cu .cu-tl li:first-child{border-top:0}.cu .cu-tl time{font:500 11.5px 'JetBrains Mono',monospace;color:var(--txt-faint);min-width:96px}" +
    ".cu .cu-ms{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.cu .cu-ms div{border:1px solid var(--line);border-radius:12px;padding:9px 12px;background:var(--surface)}.cu .cu-ms .no{opacity:.45}.cu .cu-ms small{display:block;color:var(--txt-faint)}" +
    ".cu .cu-dot{display:inline-block;min-width:24px;border-radius:7px;font:600 11px/22px 'JetBrains Mono',monospace;text-align:center;background:var(--surface);color:var(--txt-faint);border:0}.cu .cu-dot.a{background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok)}.cu .cu-dot.p{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}.cu .cu-dot.r{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger)}" +
    ".cu .cu-vide{color:var(--txt-faint);padding:18px;text-align:center}.cu .cu-bad{outline:2px solid var(--danger)}.cu .cu-note{border:1px dashed var(--line-strong,var(--line));border-radius:12px;padding:9px 12px;font-size:12.5px;color:var(--txt-soft)}" +
    "@media (max-width:900px){.cu .cu-split{grid-template-columns:1fr}.cu .cu-rt{grid-template-columns:1fr}.cu .cu-rt .eff{justify-content:flex-start}}";

  const initiales = (c) => String((c && (c.display_name || c.compte)) || "?").replace(/^agent:/, "").trim().split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((x) => x[0].toUpperCase()).join("") || "?";
  const nomDe = (c) => (c && (c.display_name || c.compte)) || "?";
  const ico = (d) => '<svg class="cu-i" viewBox="0 0 24 24"><path d="' + d + '"/></svg>';
  const PLUS = "M12 5v14M5 12h14";
  const quand = (t) => { try { return new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };
  const slug = (t) => String(t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 31);
  const motDePasse = () => { const a = "ABCDEFGHJKLMNPQRSTUVWXYZ", b = "abcdefghijkmnpqrstuvwxyz", n = "23456789", s = "-_!"; const p = (x) => x[Math.floor(Math.random() * x.length)]; let r = [p(a), p(a), p(b), p(b), p(b), p(b), p(b), p(b), p(n), p(n), p(s), p(b), p(b), p(b), p(n)]; r = r.sort(() => Math.random() - 0.5); if (!/[A-Z]/.test(r.join(""))) r[0] = p(a); return r.join(""); };

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.comptes = async function (corps, ctx) {
    if (ctx && /:console$/.test(String(ctx.ecran || ""))) { if (CASS.console) CASS.console("comptes", corps); return; }
    K.injecter();
    if (!document.getElementById("cu-css")) { const st = document.createElement("style"); st.id = "cu-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "cu"; corps.appendChild(racine);
    const S = { page: PAGES[String(ctx && ctx.ecran || "").split(":")[1]] || "u_liste", comptes: [], etat: { admins: [], groupes: [], accords: [] }, catalogue: [], dec: {}, moi: "", fiche: "", gfiche: "", onglet: "", q: "", filtre: "tous", fl: "tous", ouvert: null, draft: {}, adm: null, notif: true, droitQui: "", qui: null, journal: [], regles: "", nu: { groupes: [], modele: "Opérateur" }, ng: { membres: [], modele: "" }, charge: true, erreur: "" };
    const $ = (s) => racine.querySelector(s);
    const val = (s) => (($(s) || {}).value || "").trim();

    // ── lecture ──────────────────────────────────────────────────────────
    async function lire(cap, args) { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } }
    async function geste(cap, args, ok) { try { const r = await agir(cap, args); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(e.message || String(e), "err"); return false; } }
    const estAdmin = (c) => S.etat.admins.indexOf(c) >= 0;
    const compteDe = (c) => S.comptes.find((x) => x.compte === c) || { compte: c };
    const groupesDe = (c) => S.etat.groupes.filter((g) => g.membres.indexOf(c) >= 0);
    const groupeDe = (id) => S.etat.groupes.find((g) => g.groupe === id) || { groupe: id, libelle: id, membres: [] };
    const accordDe = (type, sujet, droit) => { const a = S.etat.accords.find((x) => x.sujet_type === type && x.sujet === sujet && x.droit === droit); return a ? (a.accord ? "accorde" : "refuse") : "herite"; };
    const modules = () => { const m = {}; S.catalogue.forEach((d) => { (m[d.module] = m[d.module] || []).push(d); }); return m; };
    async function charger() {
      const [l, e, c, m, so] = await Promise.all([lire("comptes.lister"), lire("droits.etat"), lire("droits.catalogue"), lire("comptes.moi"), lire("societes.lister")]);
      S.societes = (so && so.societes) || []; S.superadmin = !!(so && so.superadmin); S.societeActive = (so && so.societe) || "1";
      S.droitsOk = !!e; if (!e) S.erreur = "";                                // sans le droit de régler les droits fins : une vue réduite, par fonctions
      S.comptes = (l && l.comptes) || []; S.etat = e || { admins: [], groupes: [], accords: [] }; S.catalogue = (c && c.droits) || []; S.moi = (m && (m.compte || (m.profil && m.profil.compte))) || "";
      const humains = S.comptes.filter((x) => x.type !== "systeme").slice(0, 60);
      if (S.droitsOk) await Promise.all(humains.map(async (x) => { const r = await lire("droits.decisions", { compte: x.compte }); if (r) S.dec[x.compte] = r; }));
    }
    const nbOk = (c) => { const d = S.dec[c]; return d ? d.droits.filter((x) => x.accord).length : 0; };

    // ── pages ────────────────────────────────────────────────────────────
    const rien = () => "";   // la page ouverte porte déjà son fil d'Ariane (celui de la disposition) ; seules les fiches ajoutent le leur
    const fil = (a, b) => '<div class="cu-fil">' + a + " › <b>" + esc(b) + "</b></div>";
    const entete = (t, lead) => '<div><h1 title="' + esc(lead) + '" style="cursor:help">' + esc(t) + "</h1></div>";    // la légende est une infobulle, pas une ligne de plus
    const chip = (t, c) => '<span class="cu-chip ' + (c || "") + '">' + esc(t) + "</span>";
    const avatar = (c) => '<span class="cu-av">' + esc(initiales(c)) + "</span>";

    const nomSociete = (id) => { const x = (S.societes || []).find((y) => y.id === (id || "1")); return x ? x.nom : (id || "1"); };
    function pUListe() {
      const q = S.q.toLowerCase(), f = S.fl;
      const l = S.comptes.filter((c) => c.type !== "systeme" && (f === "tous" || (f === "admin" && estAdmin(c.compte)) || (f === "agent" && c.type === "agent") || (f === "off" && c.desactive)) &&
        [c.compte, c.display_name, c.role_label, groupesDe(c.compte).map((g) => g.libelle).join(" ")].join(" ").toLowerCase().indexOf(q) >= 0);
      return rien("Paramètres › Utilisateurs", "Liste des utilisateurs") + entete("Liste des utilisateurs", "Les comptes qui entrent dans Cassandra et ce qu'ils peuvent y faire. Cliquez une ligne pour ouvrir la fiche.") +
        '<div class="cu-barre"><input type="search" class="cu-grow" id="cu-q" value="' + esc(S.q) + '" placeholder="Rechercher un nom, une adresse, un groupe…" style="max-width:340px"><div class="cu-fls">' +
        [["tous", "Tous"], ["admin", "Administrateurs"], ["agent", "Agents"], ["off", "Désactivés"]].map((x) => '<button class="cu-fl' + (f === x[0] ? " on" : "") + '" data-a="fl" data-v="' + x[0] + '">' + x[1] + "</button>").join("") +
        '</div><button class="cu-btn pri" data-a="page" data-p="u_nouveau">' + ico(PLUS) + "Nouvel utilisateur</button></div>" +
        '<div class="cu-tw"><table><thead><tr><th>Utilisateur</th><th>Fonction</th><th>Société</th><th>Groupes</th><th>Droits</th><th>État</th></tr></thead><tbody>' +
        (l.map((c) => '<tr class="cu-l" data-a="fiche" data-k="' + esc(c.compte) + '"><td><div class="cu-who">' + avatar(c) + "<div><b>" + esc(nomDe(c)) + "</b><small>" + esc(c.compte) + "</small></div></div></td><td>" + esc(c.role_label || "") + "</td><td>" + esc(nomSociete(c.societe)) + "</td><td>" +
          (groupesDe(c.compte).map((g) => chip(g.libelle || g.groupe, "acc")).join(" ") || '<span class="cu-why">aucun</span>') + "</td><td>" + (estAdmin(c.compte) ? chip("tous (administrateur)", "warn") : chip(nbOk(c.compte) + " / " + ((S.dec[c.compte] || { droits: [] }).droits.length), "ok")) + "</td><td>" +
          (c.desactive ? chip("désactivé", "dng") : chip("actif", "ok")) + (c.type === "agent" ? " " + chip("agent", "info") : "") + "</td></tr>").join("") || '<tr><td colspan="6" class="cu-vide">Aucun résultat.</td></tr>') + "</tbody></table></div>";
    }

    function modeles() {
      const cat = S.catalogue, lect = cat.filter((d) => !d.sensible && /(lire|voir|consulter)$/.test(d.droit)).map((d) => d.droit), oper = cat.filter((d) => !d.sensible).map((d) => d.droit);
      return { "Lecteur": lect, "Opérateur": oper, "Administrateur délégué": cat.map((d) => d.droit), "Aucun (je règle à la main)": [] };
    }
    function pUNouveau() {
      const M = modeles();
      return rien("Paramètres › Utilisateurs", "Nouvel utilisateur") + entete("Nouvel utilisateur", "Quatre étapes : qui est-ce, à quoi a-t-il accès, sur quels sites, comment entre-t-il. Les droits se retouchent ensuite sur sa fiche.") +
        '<div class="cu-split"><div style="display:grid;gap:14px"><div class="cu-carte"><h3>① Identité</h3><div class="cu-g2"><div><label class="cu-f">Adresse e-mail (identifiant) *</label><input type="email" id="nu-id" placeholder="prenom@exemple.fr"></div><div><label class="cu-f">Nom affiché</label><input type="text" id="nu-nom" placeholder="Prénom Nom"></div><div><label class="cu-f">Fonction</label><input type="text" id="nu-fn"></div><div><label class="cu-f">Téléphone</label><input type="text" id="nu-tel"></div><div><label class="cu-f">Société *</label><select id="nu-soc"' + (S.superadmin && (S.societes || []).length > 1 ? "" : " disabled") + ">" + (S.societes || []).map((x) => '<option value="' + esc(x.id) + '"' + (x.id === (S.nu.societe || S.societeActive) ? " selected" : "") + ">" + esc(x.nom) + '</option>').join("") + '</select></div><div><label class="cu-f">Fonction dans la société</label><select id="nu-fon"><option value="">— aucune —</option>' + (S.nuFonctions || []).map((g) => '<option value="' + esc(g.fonction) + '">' + esc(g.nom) + "</option>").join("") + '</select></div></div></div>' +
        '<div class="cu-carte"><h3>② Accès</h3><div class="cu-g2"><div><label class="cu-f">Modèle de droits</label><select id="nu-mod">' + Object.keys(M).map((k) => '<option' + (S.nu.modele === k ? " selected" : "") + ">" + esc(k) + "</option>").join("") + '</select></div></div><div style="margin-top:12px"><label class="cu-f">Groupes</label><div class="cu-fls">' +
        (S.etat.groupes.map((g) => '<button class="cu-fl' + (S.nu.groupes.indexOf(g.groupe) >= 0 ? " on" : "") + '" data-a="nu-g" data-k="' + esc(g.groupe) + '">' + esc(g.libelle || g.groupe) + "</button>").join("") || '<span class="cu-why">Aucun groupe encore.</span>') + '</div></div></div>' +
        '<div class="cu-carte"><h3>③ Sites et hébergement</h3><label class="cu-f">Sites accessibles (séparés par des virgules)</label><input type="text" id="nu-sites" placeholder="www.exemple.fr, shop.exemple.fr"><div class="cu-g2" style="margin-top:12px"><div><label class="cu-f">Compte FastPanel lié</label><input type="text" id="nu-fp" placeholder="(aucun)"></div><div><label class="cu-f">Utilisateur Unix</label><input type="text" id="nu-unix" placeholder="(aucun)"></div></div><p class="cu-why" style="margin:8px 0 0">Sans site, le compte ne voit aucun site, même avec le droit de les voir.</p></div>' +
        '<div class="cu-carte"><h3>④ Entrée</h3><label class="cu-f">Mot de passe provisoire</label><div class="cu-barre"><input type="text" id="nu-mdp" class="cu-grow" value="' + esc(S.nu.mdp || (S.nu.mdp = motDePasse())) + '"><button class="cu-btn" data-a="nu-mdp">Générer</button></div>' + (S.regles ? '<p class="cu-why" style="margin:6px 0 0">' + esc(S.regles) + "</p>" : "") + "</div>" +
        '<div class="cu-barre"><button class="cu-btn pri" data-a="nu-creer">Créer l\'utilisateur</button><button class="cu-btn" data-a="page" data-p="u_liste">Annuler</button></div></div>' +
        '<div style="display:grid;gap:12px"><div class="cu-carte"><h3>Ce qui se passe</h3><ul class="cu-lst"><li>' + chip("1", "acc") + " Le compte est créé.</li><li>" + chip("2", "acc") + " Il reçoit le modèle et les groupes cochés.</li><li>" + chip("3", "acc") + " Vous arrivez sur sa fiche pour affiner ses droits.</li></ul></div></div></div>";
    }

    // la fiche d'un utilisateur : fiche / droits / groupes / journal
    function valeurPropre(c, d) { return d in S.draft ? S.draft[d] : accordDe("compte", c, d); }
    function effectif(c, droit, etat) {
      // la décision du moteur tant que rien n'est modifié ; sinon on le dit : le recalcul exact se fait à l'application
      const base = ((S.dec[c] || { droits: [] }).droits.find((x) => x.droit === droit)) || { accord: false, parce: "" };
      return { accord: base.accord, parce: base.parce, propre: base.propre };
    }
    function listeDroits(type, sujet, adm) {
      const mods = modules(), q = S.qd ? S.qd.toLowerCase() : "", filtre = S.filtre;
      const noms = Object.keys(mods).sort();
      const nbChg = (d) => (d in S.draft) && S.draft[d] !== accordDe(type, sujet, d);
      return noms.map((m, mi) => {
        let n = 0, rows = "", ok = 0;
        mods[m].forEach((d) => {
          const e = (type === "compte" ? valeurPropre(sujet, d.droit) : (d.droit in S.draft ? S.draft[d.droit] : accordDe("groupe", sujet, d.droit)));
          const r = type === "compte" ? effectif(sujet, d.droit) : { accord: e === "accorde", parce: "" };
          const accorde = adm || (type === "compte" ? (e === "accorde" || (e === "herite" && r.accord)) : e === "accorde");
          if (accorde) ok++;
          if (q && [d.libelle, d.droit, m].join(" ").toLowerCase().indexOf(q) < 0) return;
          if (filtre === "accorde" && !accorde) return; if (filtre === "refuse" && accorde) return; if (filtre === "sens" && !d.sensible) return; if (filtre === "chg" && !nbChg(d.droit)) return;
          n++;
          let eff;
          if (type === "compte") eff = '<span class="cu-chip ' + (accorde ? "ok" : "dng") + '">' + (accorde ? "✓ Autorisé" : "✕ Refusé") + '</span><span class="cu-why">' + esc(adm ? "administrateur" : (d.droit in S.draft ? "à appliquer" : r.parce || "")) + "</span>";
          else { const mem = groupeDe(sujet).membres, gagnent = mem.filter((c) => ((S.dec[c] || { droits: [] }).droits.find((x) => x.droit === d.droit) || {}).accord).length, perso = mem.filter((c) => accordDe("compte", c, d.droit) === "refuse").length;
            eff = '<span class="cu-chip ' + (mem.length && gagnent === mem.length ? "ok" : gagnent ? "warn" : "") + '">' + gagnent + " / " + mem.length + ' membres</span>' + (perso ? '<span class="cu-why">' + perso + " refus personnel</span>" : ""); }
          rows += '<div class="cu-rt' + (nbChg(d.droit) ? " chg" : "") + '" data-d="' + esc(d.droit) + '"><span class="cu-seg' + (adm ? " lock" : "") + '">' + ETATS.map((x) => '<button data-a="etat" data-v="' + x[0] + '" data-d="' + esc(d.droit) + '"' + (e === x[0] ? ' class="on"' : "") + ">" + x[1] + "</button>").join("") + "</span><div><b>" + esc(d.libelle || d.droit) + "</b> " + (d.sensible ? BOUCLIER : "") + '<span class="cu-why" style="display:block">' + esc(d.droit) + "</span></div><div class=\"eff\">" + eff + "</div></div>";
        });
        if (!n && (q || filtre !== "tous")) return "";
        const ouvert = S.ouvert === null ? mi < 2 : S.ouvert;
        return '<div class="cu-mod' + (ouvert || q || filtre !== "tous" ? " open" : "") + '" data-m="' + esc(m) + '"><div class="cu-mh" data-a="mod"><span class="nm"><svg class="cu-i car" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>' + esc(m) + '</span><span class="cnt">' + ok + " / " + mods[m].length + '</span><span class="act"><button class="cu-bulk" data-a="lot" data-m="' + esc(m) + '" data-v="accorde">Tout</button><button class="cu-bulk" data-a="lot" data-m="' + esc(m) + '" data-v="refuse">Aucun</button><button class="cu-bulk" data-a="lot" data-m="' + esc(m) + '" data-v="herite">Hériter</button></span></div><div class="cu-rights">' + rows + "</div></div>";
      }).join("") || '<div class="cu-vide">Aucun droit ne correspond.</div>';
    }
    const filtresHtml = () => '<div class="cu-barre"><input type="search" class="cu-grow" id="cu-qd" value="' + esc(S.qd || "") + '" placeholder="Chercher un droit : « supprimer », « pare-feu »…" style="max-width:340px"><div class="cu-fls">' +
      [["tous", "Tous"], ["accorde", "Autorisés"], ["refuse", "Refusés"], ["sens", "Sensibles"], ["chg", "Modifiés"]].map((x) => '<button class="cu-fl' + (S.filtre === x[0] ? " on" : "") + '" data-a="rf" data-v="' + x[0] + '">' + x[1] + "</button>").join("") +
      '</div><button class="cu-bulk" data-a="ouvrir" data-v="1">Tout dérouler</button><button class="cu-bulk" data-a="ouvrir" data-v="0">Tout replier</button></div>';
    const nbModifs = (type, sujet) => Object.keys(S.draft).filter((d) => S.draft[d] !== accordDe(type, sujet, d)).length + (type === "compte" && S.adm != null && S.adm !== estAdmin(sujet) ? 1 : 0);

    // Un utilisateur appartient à UNE société (la sienne) et peut avoir une fonction dans d'autres : il n'a alors accès qu'à ce que cette fonction lui ouvre.
    async function chargerFicheSocietes(compte) {
      S.ficheSoc = {};
      await Promise.all((S.societes || []).filter((x) => !x.archivee).map(async (x) => {
        const r = await lire("societes.fonctions", { societe: x.id }); S.erreur = "";
        const F = (r && r.fonctions) || [], actuelle = (F.find((f) => (f.membres || []).indexOf(compte) >= 0) || {}).fonction || "";
        S.ficheSoc[x.id] = { ok: !!r, fonctions: F, actuelle: actuelle };
      }));
    }
    function pFicheSocietes(c) {
      const lignes = (S.societes || []).filter((x) => !x.archivee).map((x) => {
        const f = (S.ficheSoc || {})[x.id] || { ok: false, fonctions: [], actuelle: "" };
        return "<tr><td><b>" + esc(x.nom) + "</b>" + (c.societe === x.id ? " " + chip("sa société", "acc") : "") + "</td><td>" + (f.ok ? '<select data-sf="' + esc(x.id) + '" aria-label="Fonction dans ' + esc(x.nom) + '" style="min-width:180px"><option value="">— aucune —</option>' + f.fonctions.map((g) => '<option value="' + esc(g.fonction) + '"' + (g.fonction === f.actuelle ? " selected" : "") + ">" + esc(g.nom) + "</option>").join("") + "</select>" : '<span class="cu-why">Vous ne gérez pas cette société.</span>') + "</td></tr>";
      }).join("");
      return '<div class="cu-carte"><h3>Sociétés et fonctions</h3><p class="cu-why" style="margin:0 0 10px">Sa société est celle où ses documents et son espace sont rangés. Une fonction dans une autre société lui en ouvre l’accès, sans le rendre administrateur : il ne voit alors que ce que cette fonction permet. Sans fonction, aucun accès.</p><div class="cu-tw"><table><thead><tr><th>Société</th><th>Fonction</th></tr></thead><tbody>' + (lignes || '<tr><td colspan="2" class="cu-vide">Aucune société.</td></tr>') + "</tbody></table></div></div>";
    }
    function pFiche() {
      const c = compteDe(S.fiche), tab = S.onglet || (S.droitsOk ? "droits" : "fiche"), adm = S.adm == null ? estAdmin(c.compte) : S.adm, dec = S.dec[c.compte] || { droits: [] };
      const n = nbModifs("compte", c.compte);
      const tabs = '<div class="cu-tabs">' + (S.droitsOk ? [["fiche", "Fiche"], ["soc", "Sociétés"], ["droits", "Droits"], ["groupes", "Groupes"], ["jrn", "Journal"]] : [["fiche", "Fiche"], ["soc", "Sociétés"]]).map((x) => '<button class="cu-tab' + (tab === x[0] ? " on" : "") + '" data-a="onglet" data-v="' + x[0] + '">' + x[1] + (x[0] === "droits" && n ? ' <span class="cu-chip warn">' + n + "</span>" : "") + "</button>").join("") + "</div>";
      let h = fil('Paramètres › Utilisateurs › <button data-a="page" data-p="u_liste">Liste</button>', nomDe(c)) +
        '<div class="cu-hero">' + '<span class="cu-av big">' + esc(initiales(c)) + '</span><div class="cu-m"><h2>' + esc(nomDe(c)) + "</h2><p class=\"cu-why\" style=\"margin:2px 0 6px\">" + esc([c.role_label, c.compte].filter(Boolean).join(" · ")) + '</p><div class="cu-fls">' + (estAdmin(c.compte) ? chip("Administrateur", "warn") : "") + chip(c.type || "humain") + groupesDe(c.compte).map((g) => chip(g.libelle || g.groupe, "acc")).join("") + (c.desactive ? chip("désactivé", "dng") : chip("actif", "ok")) + "</div></div>" +
        '<div class="cu-barre"><button class="cu-btn" data-a="comme" data-k="' + esc(c.compte) + '">' + ico("M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6a3 3 0 0 0 0-6") + 'Voir comme</button><button class="cu-btn" data-a="jeton" data-k="' + esc(c.compte) + '">Lien de mot de passe</button>' +
        (c.desactive ? '<button class="cu-btn" data-a="reactiver" data-k="' + esc(c.compte) + '">Réactiver</button>' : '<button class="cu-btn dng" data-a="depart" data-k="' + esc(c.compte) + '"' + (c.compte === S.moi ? " disabled" : "") + ">Désactiver</button>") + "</div></div>" + (S.jeton && S.jeton.compte === c.compte ? '<div class="cu-note">Lien à donner à la personne (72 h, un seul usage) : <b style="word-break:break-all">' + esc(S.jeton.jeton) + "</b></div>" : "") + tabs;
      if (!S.droitsOk) h = h.replace(/<button class="cu-btn" data-a="comme"[\s\S]*?<\/button>/, "");
      if (tab === "fiche") {
        const champ = (cle, lib, type) => '<div><label class="cu-f">' + esc(lib) + '</label><input id="cf-' + cle + '" type="' + (type || "text") + '" value="' + esc(c[cle] || "") + '"></div>';
        h += '<div class="cu-carte"><h3>Identité</h3><div class="cu-g2">' + champ("display_name", "Nom affiché") + champ("role_label", "Fonction") + champ("contact_email", "Courriel de contact", "email") + champ("phone", "Téléphone", "tel") + champ("lang", "Langue") + '</div></div>' +
          '<div class="cu-carte"><h3>Sites et hébergement</h3><label class="cu-f">Sites accessibles (séparés par des virgules)</label><input id="cf-sites" type="text" value="' + esc((c.sites || []).join(", ")) + '"><div class="cu-g2" style="margin-top:12px">' + champ("fp_account", "Compte FastPanel lié") + '<div><label class="cu-f">Utilisateur Unix</label><input type="text" value="' + esc(c.unix_user || "") + '" disabled></div></div></div><div class="cu-barre"><button class="cu-btn pri" data-a="profil" data-k="' + esc(c.compte) + '">Enregistrer</button></div>';
      } else if (tab === "soc") {
        h += pFicheSocietes(c);
      } else if (tab === "groupes") {
        h += '<div class="cu-carte"><h3>Appartenance</h3><div class="cu-fls">' + (S.etat.groupes.map((g) => '<button class="cu-fl' + (g.membres.indexOf(c.compte) >= 0 ? " on" : "") + '" data-a="membre" data-k="' + esc(g.groupe) + '" data-p="' + (g.membres.indexOf(c.compte) >= 0 ? 0 : 1) + '">' + esc(g.libelle || g.groupe) + "</button>").join("") || '<span class="cu-why">Aucun groupe : créez-en un.</span>') + '</div><p class="cu-why" style="margin:10px 0 0">Cliquer ajoute ou retire le groupe, et les droits se recalculent aussitôt.</p></div>';
      } else if (tab === "jrn") {
        h += '<div class="cu-carte"><h3>Ce qui a changé pour ce compte</h3>' + journalHtml(S.journal.filter((e) => e.objet === c.compte || (e.donnees && e.donnees.sujet === c.compte))) + "</div>";
      } else {
        const ok = adm ? dec.droits.length : dec.droits.filter((d) => { const e = valeurPropre(c.compte, d.droit); return e === "accorde" || (e === "herite" && d.accord && !(d.droit in S.draft)); }).length;
        const sens = dec.droits.filter((d) => d.sensible && (adm || valeurPropre(c.compte, d.droit) === "accorde" || (valeurPropre(c.compte, d.droit) === "herite" && d.accord))).length;
        h += '<div class="cu-split"><div style="display:grid;gap:12px">' +
          '<div class="cu-adm"><div><b>Administrateur</b><br><span class="cu-why">Un administrateur a tous les droits, sans exception : les réglages sont suspendus tant que ce commutateur est actif.</span></div><button class="cu-sw' + (adm ? " on" : "") + '" data-a="adm" aria-label="Administrateur" aria-pressed="' + adm + '"></button></div>' +
          '<div class="cu-kpis"><div class="cu-kpi ok"><b>' + ok + '</b><span>autorisés</span></div><div class="cu-kpi dng"><b>' + (dec.droits.length - ok) + '</b><span>refusés ou non attribués</span></div><div class="cu-kpi"><b>' + dec.droits.filter((d) => d.propre).length + '</b><span>réglés sur ce compte</span></div><div class="cu-kpi warn"><b>' + sens + "</b><span>sensibles autorisés</span></div></div>" +
          filtresHtml() + "<div>" + listeDroits("compte", c.compte, adm) + "</div>" +
          '<div class="cu-bar' + (n ? " on" : "") + '"><b>' + n + " modification" + (n > 1 ? "s" : "") + " non appliquée" + (n > 1 ? "s" : "") + '</b><span class="cu-grow" style="opacity:.7;font-size:12.5px">Rien n\'est appliqué tant que vous n\'avez pas validé.</span><label><input type="checkbox" id="cu-notif"' + (S.notif ? " checked" : "") + ' style="width:auto"> Prévenir l\'intéressé</label><button class="cu-btn sm" data-a="annuler-draft">Annuler</button><button class="cu-btn sm pri" data-a="appliquer">Appliquer</button></div></div>' +
          '<div style="display:grid;gap:12px"><div class="cu-carte"><h3>Partir d\'un modèle</h3><select id="cu-tpl"><option>— choisir —</option>' + Object.keys(modeles()).map((k) => "<option>" + esc(k) + "</option>").join("") + '</select><p class="cu-why" style="margin:8px 0 0">Prépare un jeu de droits à retoucher avant d\'appliquer.</p></div>' +
          '<div class="cu-carte"><h3>Copier depuis…</h3><select id="cu-cpy"><option value="">— un autre utilisateur —</option>' + S.comptes.filter((x) => x.compte !== c.compte && x.type === "humain").map((x) => '<option value="' + esc(x.compte) + '">' + esc(nomDe(x)) + "</option>").join("") + "</select></div>" +
          '<div class="cu-carte"><h3>Comment lire</h3><ul class="cu-lst"><li><span class="cu-seg"><button class="on" data-v="herite">Hérité</button></span>suit les groupes, sinon le défaut</li><li><span class="cu-seg"><button class="on" data-v="accorde">Accordé</button></span>forcé pour ce compte</li><li><span class="cu-seg"><button class="on" data-v="refuse">Refusé</button></span>forcé, même si un groupe l\'accorde</li><li>' + BOUCLIER + "droit sensible : journalisé à chaque usage</li></ul></div></div></div>";
      }
      return h;
    }

    // groupes
    function pGListe() {
      return rien("Paramètres › Groupes", "Liste des groupes") + entete("Liste des groupes", "Chaque groupe porte ses droits ; ses membres les reçoivent, sauf refus posé sur leur compte. Un refus de groupe l'emporte sur un octroi.") +
        '<div class="cu-barre"><button class="cu-btn" data-a="page" data-p="matrice">Matrice des droits</button><button class="cu-btn pri" data-a="page" data-p="g_nouveau">' + ico(PLUS) + "Nouveau groupe</button></div>" +
        '<div class="cu-tw"><table><thead><tr><th>Groupe</th><th>Membres</th><th>Droits accordés</th><th>Refus posés</th></tr></thead><tbody>' +
        (S.etat.groupes.map((g) => { const ac = S.etat.accords.filter((a) => a.sujet_type === "groupe" && a.sujet === g.groupe);
          return '<tr class="cu-l" data-a="gfiche" data-k="' + esc(g.groupe) + '"><td><div class="cu-who"><span class="cu-av" style="border-radius:11px">' + esc((g.libelle || g.groupe)[0].toUpperCase()) + "</span><div><b>" + esc(g.libelle || g.groupe) + "</b><small>" + esc(g.description || g.groupe) + "</small></div>" + (g.societe ? " " + chip("fonction · " + nomSociete(g.societe), "info") : "") + "</div></td><td>" + (g.membres.length ? g.membres.map((m) => '<span class="cu-av" style="width:26px;height:26px;font-size:10px;display:inline-grid;margin-right:-6px;border:2px solid var(--surface)">' + esc(initiales(compteDe(m))) + "</span>").join("") + ' <span class="cu-why" style="margin-left:10px">' + g.membres.length + "</span>" : '<span class="cu-why">vide</span>') + "</td><td>" + chip(ac.filter((a) => a.accord).length, "ok") + "</td><td>" + chip(ac.filter((a) => !a.accord).length, ac.some((a) => !a.accord) ? "dng" : "") + "</td></tr>"; }).join("") || '<tr><td colspan="4" class="cu-vide">Aucun groupe. Un groupe rassemble des utilisateurs pour leur donner les mêmes droits d\'un coup.</td></tr>') + "</tbody></table></div>";
    }
    function pGNouveau() {
      return rien("Paramètres › Groupes", "Nouveau groupe") + entete("Nouveau groupe", "Un groupe réunit des utilisateurs qui font le même travail : on règle les droits une fois, et chacun les reçoit.") +
        '<div class="cu-split"><div style="display:grid;gap:14px"><div class="cu-carte"><div class="cu-g2"><div><label class="cu-f">Nom du groupe *</label><input type="text" id="ng-nom" placeholder="Comptabilité"></div><div><label class="cu-f">Description</label><input type="text" id="ng-desc" placeholder="À quoi sert ce groupe"></div></div>' +
        '<div class="cu-g2" style="margin-top:12px"><div><label class="cu-f">Partir d\'un modèle</label><select id="ng-mod"><option value="">— vide —</option>' + Object.keys(modeles()).filter((k) => k.indexOf("Aucun") !== 0).map((k) => "<option>" + esc(k) + "</option>").join("") + '</select></div><div><label class="cu-f">Ou copier un groupe</label><select id="ng-cp"><option value="">— aucun —</option>' + S.etat.groupes.map((g) => '<option value="' + esc(g.groupe) + '">' + esc(g.libelle || g.groupe) + "</option>").join("") + "</select></div></div>" +
        '<div style="margin-top:12px"><label class="cu-f">Membres de départ</label><div class="cu-fls">' + (S.comptes.filter((c) => c.type === "humain").map((c) => '<button class="cu-fl' + (S.ng.membres.indexOf(c.compte) >= 0 ? " on" : "") + '" data-a="ng-m" data-k="' + esc(c.compte) + '">' + esc(nomDe(c)) + "</button>").join("") || '<span class="cu-why">Aucun utilisateur.</span>') + '</div></div></div>' +
        '<div class="cu-barre"><button class="cu-btn pri" data-a="ng-creer">Créer le groupe</button><button class="cu-btn" data-a="page" data-p="g_liste">Annuler</button></div></div></div>';
    }
    function pGFiche() {
      const g = groupeDe(S.gfiche), tab = S.onglet || "membres", mem = g.membres, n = nbModifs("groupe", g.groupe);
      const ac = S.etat.accords.filter((a) => a.sujet_type === "groupe" && a.sujet === g.groupe);
      let h = fil('Paramètres › Groupes › <button data-a="page" data-p="g_liste">Liste</button>', g.libelle || g.groupe) +
        '<div class="cu-hero"><span class="cu-av big" style="border-radius:18px">' + esc((g.libelle || g.groupe)[0].toUpperCase()) + '</span><div class="cu-m"><h2>' + esc(g.libelle || g.groupe) + '</h2><p class="cu-why" style="margin:2px 0 0">' + esc(g.description || "") + " " + mem.length + " membre" + (mem.length > 1 ? "s" : "") + '</p></div><div class="cu-barre"><button class="cu-btn" data-a="g-renommer" data-k="' + esc(g.groupe) + '">Renommer</button><button class="cu-btn dng" data-a="g-suppr" data-k="' + esc(g.groupe) + '">Supprimer</button></div></div>' +
        '<div class="cu-tabs">' + [["membres", "Membres"], ["droits", "Droits du groupe"], ["jrn", "Journal"]].map((x) => '<button class="cu-tab' + (tab === x[0] ? " on" : "") + '" data-a="onglet" data-v="' + x[0] + '">' + x[1] + (x[0] === "droits" && n ? ' <span class="cu-chip warn">' + n + "</span>" : "") + "</button>").join("") + "</div>";
      if (tab === "membres") h += '<div class="cu-carte"><h3>Membres</h3><div style="display:grid;gap:8px">' + (mem.map((m) => '<div class="cu-who" style="justify-content:space-between;border:1px solid var(--line);border-radius:12px;padding:8px 12px"><div class="cu-who">' + avatar(compteDe(m)) + '<div><b><a href="#" data-a="fiche" data-k="' + esc(m) + '">' + esc(nomDe(compteDe(m))) + "</a></b><small>" + esc(compteDe(m).role_label || m) + '</small></div></div><button class="cu-btn sm" data-a="retirer" data-k="' + esc(m) + '">Retirer</button></div>').join("") || '<span class="cu-why">Aucun membre.</span>') + '</div><div class="cu-barre" style="margin-top:12px"><select id="g-add" style="max-width:280px"><option value="">Ajouter un utilisateur…</option>' + S.comptes.filter((c) => c.type === "humain" && mem.indexOf(c.compte) < 0).map((c) => '<option value="' + esc(c.compte) + '">' + esc(nomDe(c)) + "</option>").join("") + '</select><button class="cu-btn" data-a="ajouter">Ajouter</button></div></div>';
      else if (tab === "jrn") h += '<div class="cu-carte">' + journalHtml(S.journal.filter((e) => e.donnees && e.donnees.sujet === g.groupe || e.objet === g.groupe)) + "</div>";
      else h += '<div class="cu-kpis"><div class="cu-kpi ok"><b>' + ac.filter((a) => a.accord).length + '</b><span>accordés au groupe</span></div><div class="cu-kpi dng"><b>' + ac.filter((a) => !a.accord).length + "</b><span>refus posés</span></div></div>" + filtresHtml() + "<div>" + listeDroits("groupe", g.groupe, false) + "</div>" +
        '<div class="cu-bar' + (n ? " on" : "") + '"><b>' + n + " modification" + (n > 1 ? "s" : "") + '</b><span class="cu-grow" style="opacity:.7;font-size:12.5px">Les ' + mem.length + ' membres sont concernés dès l\'application.</span><button class="cu-btn sm" data-a="annuler-draft">Annuler</button><button class="cu-btn sm pri" data-a="appliquer">Appliquer</button></div>';
      return h;
    }

    // matrice, qui peut, journal
    function pMatrice() {
      const mode = S.mx || "g", mods = modules(), noms = Object.keys(mods).sort(), cols = mode === "g" ? S.etat.groupes.map((g) => ({ id: g.groupe, nom: g.libelle || g.groupe })) : S.comptes.filter((c) => c.type === "humain").map((c) => ({ id: c.compte, nom: nomDe(c) }));
      const cell = (m, col) => { const l = mods[m]; let a = 0, refus = false;
        l.forEach((d) => { if (mode === "g") { const e = accordDe("groupe", col.id, d.droit); if (e === "accorde") a++; if (e === "refuse") refus = true; } else { const x = (S.dec[col.id] || { droits: [] }).droits.find((y) => y.droit === d.droit); if (x && x.accord) a++; if (accordDe("compte", col.id, d.droit) === "refuse") refus = true; } });
        return '<td><button class="cu-dot ' + (refus ? "r" : a === l.length ? "a" : a ? "p" : "") + '" data-a="cellule" data-m="' + esc(m) + '" data-k="' + esc(col.id) + '">' + (refus ? "!" : a) + "</button></td>"; };
      return rien("Paramètres › Groupes", "Matrice des droits") + entete("Matrice des droits", "Qui peut quoi, d'un coup d'œil. Cliquez une case pour descendre au détail du module.") +
        '<div class="cu-barre"><div class="cu-fls"><button class="cu-fl' + (mode === "g" ? " on" : "") + '" data-a="mx" data-v="g">Groupes</button><button class="cu-fl' + (mode === "u" ? " on" : "") + '" data-a="mx" data-v="u">Utilisateurs</button></div><span class="cu-why">Légende : le nombre de droits du module · <b>!</b> un refus posé</span></div>' +
        '<div class="cu-carte"><h3>' + ico("M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z") + " Couverture des droits " + chip(noms.length + " modules déclarent leurs droits", "ok") + '</h3><p class="cu-why" style="margin:0">Règle du noyau : <b>un module qui ne déclare aucun droit n\'est pas installé.</b> Chaque action d\'un module peut ainsi être permise ou refusée à un compte, à un groupe.</p></div>' +
        '<div class="cu-tw"><table><thead><tr><th>Module</th>' + cols.map((c) => "<th>" + esc(c.nom) + "</th>").join("") + "</tr></thead><tbody>" + noms.map((m) => "<tr><td><b>" + esc(m) + "</b> " + (mods[m].some((d) => d.sensible) ? BOUCLIER : "") + "</td>" + cols.map((c) => cell(m, c)).join("") + "</tr>").join("") + "</tbody></table></div>";
    }
    function pQui() {
      const id = S.droitQui || (S.catalogue[0] || {}).droit || "", mods = modules();
      return rien("Paramètres › Groupes", "Qui peut… ?") + entete("Qui peut… ?", "Choisissez un droit : voici tous les comptes qui peuvent l'exercer, et pourquoi. C'est l'audit en une question.") +
        '<div class="cu-barre"><select id="qui-d" style="max-width:440px">' + Object.keys(mods).sort().map((m) => '<optgroup label="' + esc(m) + '">' + mods[m].map((d) => '<option value="' + esc(d.droit) + '"' + (d.droit === id ? " selected" : "") + ">" + esc(d.libelle || d.droit) + "</option>").join("") + "</optgroup>").join("") + "</select></div>" +
        '<div class="cu-tw"><table><thead><tr><th>Compte</th><th>Peut ?</th><th>Pourquoi</th></tr></thead><tbody>' + ((S.qui || []).map((x) => '<tr class="cu-l" data-a="fiche" data-k="' + esc(x.compte) + '"><td><div class="cu-who">' + avatar({ compte: x.compte, display_name: x.nom }) + "<b>" + esc(x.nom) + "</b>" + (x.desactive ? " " + chip("désactivé", "dng") : "") + '</div></td><td><span class="cu-chip ' + (x.accord ? "ok" : "dng") + '">' + (x.accord ? "✓ Oui" : "✕ Non") + '</span></td><td class="cu-why">' + esc(x.parce) + "</td></tr>").join("") || '<tr><td colspan="3" class="cu-vide">Choisissez un droit.</td></tr>') + "</tbody></table></div>";
    }
    function texteJournal(e) {
      const d = e.donnees || {}, qui = e.agent ? e.acteur : (nomDe(compteDe(e.par)) || "un utilisateur");
      if (e.type === "droit.change") {
        const lib = { accorde: "accordé", refuse: "refusé", herite: "hérité" };
        if (d.changes || d.admin && Array.isArray(d.admin)) return "<b>" + esc(qui) + "</b> a réglé " + (d.sujet_type === "groupe" ? "le groupe" : "le compte") + " <b>" + esc(d.sujet) + "</b> : " + esc(((d.changes || []).slice(0, 3).map((c) => c.droit + " → " + lib[c.a]).join(" ; ")) + ((d.changes || []).length > 3 ? " (+" + ((d.changes || []).length - 3) + ")" : "") + (Array.isArray(d.admin) ? (d.changes && d.changes.length ? " ; " : "") + "administrateur : " + (d.admin[1] ? "oui" : "non") : ""));
        if (d.droit) return "<b>" + esc(qui) + "</b> a réglé " + (d.sujet_type === "groupe" ? "le groupe" : "le compte") + " <b>" + esc(d.sujet) + "</b> : " + esc(d.droit + " → " + (lib[d.a] || d.a));
        if ("membre" in d) return "<b>" + esc(qui) + "</b> a " + (d.membre ? "ajouté" : "retiré") + " <b>" + esc(d.compte) + "</b> " + (d.membre ? "au" : "du") + " groupe <b>" + esc(d.groupe) + "</b>";
        if ("supprime" in d) return "<b>" + esc(qui) + "</b> a " + (d.supprime ? "supprimé" : "créé ou modifié") + " le groupe <b>" + esc(d.groupe) + "</b>";
        if ("admin" in d) return "<b>" + esc(qui) + "</b> a " + (d.admin ? "nommé administrateur" : "retiré l'administration à") + " <b>" + esc(d.compte) + "</b>";
        return "<b>" + esc(qui) + "</b> : changement de droits — <b>" + esc(e.objet) + "</b>";
      }
      return "<b>" + esc(qui) + "</b> : " + esc(({ "compte.cree": "compte créé", "compte.modifie": "compte modifié", "compte.supprime": "compte supprimé", "compte.restaure": "compte restauré", "compte.desactive": "compte désactivé", "compte.reactive": "compte réactivé" })[e.type] || e.type) + " — <b>" + esc(e.objet) + "</b>";
    }
    function journalHtml(l) { return '<ul class="cu-tl">' + (l.map((e) => "<li><time>" + esc(quand(e.ts)) + "</time><span>" + (e.agent ? '<span class="cu-chip info">Agent</span> ' : '<span class="cu-chip">Humain</span> ') + texteJournal(e) + "</span></li>").join("") || '<li><span class="cu-why">Rien d\'enregistré.</span></li>') + "</ul>"; }
    function pJournal() { return rien("Paramètres › Groupes", "Journal des droits") + entete("Journal des droits", "Chaque changement est inscrit : qui l'a fait (un humain ou un agent) et sur quoi. Chaque réglage se défait depuis le journal des gestes.") + '<div class="cu-carte">' + journalHtml(S.journal) + "</div>"; }

    function dessiner() {
      dessinerPlein();
      if (!S.droitsOk && S.page === "u_nouveau") { const c2 = Array.from(racine.querySelectorAll(".cu-carte")).find((n) => /② Accès/.test(n.textContent)); if (c2) c2.remove(); }
    }
    function dessinerPlein() {
      let h;
      if (S.charge) h = '<div class="cu-vide">Lecture…</div>';
      else if (S.erreur && !S.comptes.length) h = '<div class="cu-carte"><h3>La gestion des utilisateurs ne répond pas</h3><p class="cu-why">' + esc(S.erreur) + "</p></div>";
      else h = ({ u_liste: pUListe, u_nouveau: pUNouveau, u_fiche: pFiche, g_liste: pGListe, g_nouveau: pGNouveau, g_fiche: pGFiche, matrice: pMatrice, qui: pQui, journal: pJournal }[S.page] || pUListe)();
      racine.innerHTML = h;
    }
    async function chargerFonctionsNu(soc) { const r = await lire("societes.fonctions", { societe: soc }); S.erreur = ""; S.nuFonctions = (r && r.fonctions) || []; }
    async function aller(page, plus) {
      if (Object.keys(S.draft).length || S.adm != null) { S.draft = {}; S.adm = null; }
      Object.assign(S, plus || {}); S.page = page; S.erreur = "";
      if (page === "u_nouveau" && !S.regles) { const r = await lire("comptes.regles_mdp"); S.regles = r ? r.legende || "" : ""; }
      if (page === "qui") await chargerQui();
      if (page === "u_fiche" && S.fiche) await chargerFicheSocietes(S.fiche);
      if (page === "u_nouveau") await chargerFonctionsNu(S.nu.societe || S.societeActive);
      if (page === "journal" || S.onglet === "jrn") await chargerJournal();
      dessiner();
    }
    async function chargerQui() { const id = S.droitQui || (S.catalogue[0] || {}).droit; if (!id) { S.qui = []; return; } S.droitQui = id; const r = await lire("droits.qui_peut", { droit: id }); S.qui = (r && (r.comptes || r.resultat || r)) || []; if (!Array.isArray(S.qui)) S.qui = []; }
    async function chargerJournal() { const r = await lire("droits.journal", { limite: 200 }); S.journal = (r && (r.journal || r.evenements || r)) || []; if (!Array.isArray(S.journal)) S.journal = []; }
    async function recharger() { await charger(); if (S.page === "journal" || S.onglet === "jrn") await chargerJournal(); if (S.page === "qui") await chargerQui(); dessiner(); }

    // ── les gestes ───────────────────────────────────────────────────────
    function modale(html, surMontage) {
      const v = document.createElement("div"); v.className = "kit-v"; v.style.zIndex = 9999; const m = document.createElement("div"); m.className = "kit-m cu"; m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true"); m.innerHTML = html;
      const clore = () => { v.remove(); m.remove(); }; v.addEventListener("click", clore); m.addEventListener("click", (e) => { if (e.target.closest("[data-c]")) clore(); });
      document.body.appendChild(v); document.body.appendChild(m); if (surMontage) surMontage(m, clore); return { m, clore };
    }
    async function appliquer() {
      const type = S.page === "g_fiche" ? "groupe" : "compte", sujet = type === "groupe" ? S.gfiche : S.fiche;
      const accords = {}; Object.keys(S.draft).forEach((d) => { if (S.draft[d] !== accordDe(type, sujet, d)) accords[d] = S.draft[d]; });
      const admin = type === "compte" && S.adm != null && S.adm !== estAdmin(sujet) ? S.adm : null;
      if (!Object.keys(accords).length && admin === null) return;
      const sens = Object.keys(accords).filter((d) => accords[d] === "accorde" && (S.catalogue.find((x) => x.droit === d) || {}).sensible);
      if (sens.length || admin === true) {
        const noms = sens.map((d) => "<li>" + esc((S.catalogue.find((x) => x.droit === d) || {}).libelle || d) + "</li>").join("");
        if (!await confirmer(admin === true ? "Nommer administrateur ?" : "Accorder des droits sensibles ?", (admin === true ? '<p class="note">Un administrateur a tous les droits, sans exception.</p>' : "") + (sens.length ? '<p class="note">Ces droits sont sensibles (chaque usage est journalisé)' + (type === "groupe" ? " ; les " + groupeDe(sujet).membres.length + " membre(s) du groupe les recevront" : "") + ' :</p><ul class="lst">' + noms + "</ul>" : ""), "Appliquer", true)) return;
      }
      let r;
      try { r = await agir("droits.appliquer", { sujet_type: type, sujet, accords, admin, prevenir: S.notif }); }
      catch (e) {
        const msg = e.message || String(e);
        if (/confirmation renforcée/.test(msg)) { if (!await confirmer("Confirmation renforcée", '<p class="note">' + esc(msg) + "</p>", "Appliquer quand même", true)) return; try { r = await agir("droits.appliquer", { sujet_type: type, sujet, accords, admin, prevenir: S.notif, confirme: true }); } catch (e2) { dire(e2.message || String(e2), "err"); return; } }
        else { dire(msg, "err"); S.adm = null; dessiner(); return; }
      }
      S.draft = {}; S.adm = null; dire((Object.keys(accords).length + (admin !== null ? 1 : 0)) + " réglage(s) appliqué(s), journalisé(s)" + (type === "compte" && S.notif ? " ; l'intéressé est prévenu." : "."), "ok");
      await recharger();
    }
    function depart(compte) {
      const c = compteDe(compte), autres = S.comptes.filter((x) => x.type === "humain" && x.compte !== compte && !x.desactive), ag = S.comptes.filter((x) => x.type === "agent" && x.invite_par === compte);
      modale('<h2>Départ de ' + esc(nomDe(c)) + '</h2><p class="cu-why">Désactiver coupe l\'accès, rien n\'est supprimé. Dites ce que deviennent ses affaires.</p><div class="cu-kpis"><div class="cu-kpi"><b>' + (c.sites || []).length + '</b><span>sites</span></div><div class="cu-kpi"><b>' + ag.length + '</b><span>agents invités</span></div></div>' +
        '<div><label class="cu-f">Ses sites passent à…</label><select id="dp-to"><option value="">Personne (les sites restent sans propriétaire)</option>' + autres.map((x) => '<option value="' + esc(x.compte) + '">' + esc(nomDe(x)) + "</option>").join("") + "</select></div>" +
        (ag.length ? '<div><label class="cu-f">Ses agents invités</label><select id="dp-ag"><option value="revoquer">Révoquer (ils n\'ont plus d\'invitant)</option><option value="reattribuer">Les réattribuer au compte destinataire</option></select></div>' : "") +
        '<ul class="cu-lst"><li>' + chip("✓", "ok") + " Ses sessions ouvertes sont fermées</li><li>" + chip("✓", "ok") + " Il n'entre plus ; « Défaire » ou « Réactiver » le rend tel quel</li><li>" + chip("i", "info") + " Les modules qui gardent des données par compte reçoivent l'événement compte.desactive</li></ul>" +
        '<div class="acts"><button class="cu-btn" data-c="non">Annuler</button><button class="cu-btn dng" id="dp-ok">Désactiver</button></div>', (m, clore) => {
        m.querySelector("#dp-ok").addEventListener("click", async () => { const vers = m.querySelector("#dp-to").value, agents = (m.querySelector("#dp-ag") || {}).value || "revoquer"; if (agents === "reattribuer" && !vers) { dire("Choisissez le compte qui reçoit les agents.", "err"); return; } clore(); if (await geste("comptes.desactiver", { compte, vers, agents }, nomDe(c) + " est désactivé.")) recharger(); });
      });
    }
    async function voirComme(compte) {
      const r = await lire("droits.voir_comme", { compte }); if (!r) { dire(S.erreur, "err"); return; }
      modale("<h2>Vous voyez Cassandra comme " + esc(nomDe(compteDe(compte))) + '</h2><div class="cu-note"><b>Structure seulement.</b> Vous voyez quels modules ce compte ouvre et combien de droits il y détient — jamais son contenu : ses messages, son agenda et ses documents restent à lui. Administrer un compte, ce n\'est pas le lire.</div><div class="cu-ms">' +
        (r.modules || []).map((m) => '<div class="' + (m.accordes || r.admin ? "" : "no") + '"><b>' + esc(m.nom) + "</b><small>" + (r.admin ? "tous les droits (administrateur)" : m.accordes ? m.accordes + " / " + m.total + " droits" : "masqué") + "</small></div>").join("") + '</div><div class="acts"><button class="cu-btn pri" data-c="oui">Quitter ce mode</button></div>');
    }
    function lotDe(m, v) { (modules()[m] || []).forEach((d) => { S.draft[d.droit] = v; }); }

    racine.addEventListener("click", async (e) => {
      const a = e.target.closest("[data-a]"); if (!a) return;
      const k = a.dataset.a, cle = a.dataset.k; if (a.tagName === "A") e.preventDefault();
      if (k === "page") await aller(a.dataset.p, { fiche: "", gfiche: "", onglet: "" });
      else if (k === "fiche") await aller("u_fiche", { fiche: cle, onglet: "droits", filtre: "tous", qd: "", jeton: null });
      else if (k === "gfiche") await aller("g_fiche", { gfiche: cle, onglet: "membres", filtre: "tous", qd: "" });
      else if (k === "fl") { S.fl = a.dataset.v; dessiner(); }
      else if (k === "rf") { S.filtre = a.dataset.v; dessiner(); }
      else if (k === "onglet") { S.onglet = a.dataset.v; if (a.dataset.v === "jrn") await chargerJournal(); dessiner(); }
      else if (k === "ouvrir") { S.ouvert = a.dataset.v === "1"; dessiner(); }
      else if (k === "mod") { if (e.target.closest(".cu-bulk")) return; a.parentElement.classList.toggle("open"); }
      else if (k === "lot") { lotDe(a.dataset.m, a.dataset.v); dessiner(); e.stopPropagation(); }
      else if (k === "etat") { S.draft[a.dataset.d] = a.dataset.v; dessiner(); }
      else if (k === "adm") { S.adm = !(S.adm == null ? estAdmin(S.fiche) : S.adm); dessiner(); }
      else if (k === "annuler-draft") { S.draft = {}; S.adm = null; dessiner(); }
      else if (k === "appliquer") await appliquer();
      else if (k === "profil") { const d = { compte: cle }; ["display_name", "role_label", "contact_email", "phone", "lang", "fp_account"].forEach((c) => { d[c] = val("#cf-" + c); }); d.sites = val("#cf-sites").split(/[\s,;]+/).filter(Boolean); if (await geste("comptes.modifier", d, "Fiche enregistrée.")) recharger(); }
      else if (k === "membre") { if (await geste("droits.membre", { compte: S.fiche, groupe: cle, present: a.dataset.p === "1" })) await recharger(); }
      else if (k === "jeton") { const r = await lire("comptes.creer_jeton", { compte: cle, heures: 72 }); if (r) { S.jeton = r; dessiner(); } else dire(S.erreur, "err"); }
      else if (k === "depart") depart(cle);
      else if (k === "reactiver") { if (await geste("comptes.reactiver", { compte: cle }, "Compte réactivé.")) recharger(); }
      else if (k === "comme") await voirComme(cle);
      else if (k === "nu-g") { const i = S.nu.groupes.indexOf(cle); if (i >= 0) S.nu.groupes.splice(i, 1); else S.nu.groupes.push(cle); a.classList.toggle("on"); }
      else if (k === "nu-mdp") { S.nu.mdp = motDePasse(); $("#nu-mdp").value = S.nu.mdp; }
      else if (k === "nu-creer") {
        const id = val("#nu-id"), mdp = val("#nu-mdp"); $("#nu-id").classList.toggle("cu-bad", !id); if (!id || !mdp) { dire("Il faut une adresse e-mail et un mot de passe.", "err"); return; }
        const args = { compte: id, mot_de_passe: mdp, sites: val("#nu-sites").split(/[\s,;]+/).filter(Boolean), unix_user: val("#nu-unix"), display_name: val("#nu-nom"), role_label: val("#nu-fn"), phone: val("#nu-tel"), fp_account: val("#nu-fp"), societe: val("#nu-soc") };
        if (!await geste("comptes.creer", args)) return;
        const fon = val("#nu-fon"), socNu = val("#nu-soc") || S.societeActive;
        if (fon) await geste("societes.affecter", { societe: socNu, utilisateur: id.toLowerCase(), fonction: fon });
        if (S.droitsOk) {
          for (const g of S.nu.groupes) await geste("droits.membre", { compte: id.toLowerCase(), groupe: g, present: true });
          const M = modeles(), mod = val("#nu-mod"), liste = M[mod] || [], accords = {}; liste.forEach((d) => { accords[d] = "accorde"; });
          if (Object.keys(accords).length) await geste("droits.appliquer", { sujet_type: "compte", sujet: id.toLowerCase(), accords, prevenir: false });
        }
        dire(nomDe({ compte: id, display_name: args.display_name }) + " est créé. Affinez ses droits ci-dessous.", "ok"); S.nu = { groupes: [], modele: "Opérateur" }; await charger(); await aller("u_fiche", { fiche: id.toLowerCase(), onglet: S.droitsOk ? "droits" : "soc", filtre: "tous", qd: "" });
      }
      else if (k === "ng-m") { const i = S.ng.membres.indexOf(cle); if (i >= 0) S.ng.membres.splice(i, 1); else S.ng.membres.push(cle); a.classList.toggle("on"); }
      else if (k === "ng-creer") {
        const nom = val("#ng-nom"); $("#ng-nom").classList.toggle("cu-bad", !nom); if (!nom) { dire("Le nom du groupe est obligatoire.", "err"); return; }
        let id = slug(nom) || "groupe"; while (S.etat.groupes.some((g) => g.groupe === id)) id += "_2";
        if (!await geste("droits.groupe", { groupe: id, libelle: nom, description: val("#ng-desc") })) return;
        for (const c of S.ng.membres) await geste("droits.membre", { compte: c, groupe: id, present: true });
        const cp = val("#ng-cp"), md = val("#ng-mod"), accords = {};
        if (cp) S.etat.accords.filter((x) => x.sujet_type === "groupe" && x.sujet === cp).forEach((x) => { accords[x.droit] = x.accord ? "accorde" : "refuse"; }); else (modeles()[md] || []).forEach((d) => { accords[d] = "accorde"; });
        if (Object.keys(accords).length) await geste("droits.appliquer", { sujet_type: "groupe", sujet: id, accords });
        dire("Groupe « " + nom + " » créé. Réglez ses droits.", "ok"); S.ng = { membres: [], modele: "" }; await charger(); await aller("g_fiche", { gfiche: id, onglet: "droits", filtre: "tous", qd: "" });
      }
      else if (k === "ajouter") { const c = val("#g-add"); if (c && await geste("droits.membre", { compte: c, groupe: S.gfiche, present: true })) await recharger(); }
      else if (k === "retirer") { if (await geste("droits.membre", { compte: cle, groupe: S.gfiche, present: false })) await recharger(); }
      else if (k === "g-renommer") { const g = groupeDe(cle); modale('<h2>Renommer le groupe</h2><input id="gr-nom" type="text" value="' + esc(g.libelle || g.groupe) + '"><div class="acts"><button class="cu-btn" data-c="non">Annuler</button><button class="cu-btn pri" id="gr-ok">Valider</button></div>', (m, clore) => { m.querySelector("#gr-ok").addEventListener("click", async () => { const n = m.querySelector("#gr-nom").value.trim(); if (!n) return; clore(); if (await geste("droits.groupe", { groupe: cle, libelle: n, description: g.description || "" }, "Groupe renommé.")) recharger(); }); }); }
      else if (k === "g-suppr") { if (!await confirmer("Supprimer le groupe « " + cle + " » ?", '<p class="note">Ses membres n\'en font plus partie et ses accords disparaissent. « Défaire » le rend.</p>', "Supprimer", true)) return; if (await geste("droits.groupe", { groupe: cle, supprimer: true }, "Groupe supprimé.")) { await charger(); await aller("g_liste", { gfiche: "" }); } }
      else if (k === "mx") { S.mx = a.dataset.v; dessiner(); }
      else if (k === "cellule") { S.qd = a.dataset.m; S.filtre = "tous"; S.ouvert = true; if (S.mx === "u") await aller("u_fiche", { fiche: a.dataset.k, onglet: "droits" }); else await aller("g_fiche", { gfiche: a.dataset.k, onglet: "droits" }); }
    });
    racine.addEventListener("change", async (e) => {
      const t = e.target;
      if (t.dataset.sf) { if (await geste("societes.affecter", { societe: t.dataset.sf, utilisateur: S.fiche, fonction: t.value }, "Fonction donnée.")) { await chargerFicheSocietes(S.fiche); } dessiner(); return; }
      if (t.id === "nu-soc") { S.nu.societe = t.value; await chargerFonctionsNu(t.value); dessiner(); return; }
      if (t.id === "cu-notif") S.notif = t.checked;
      else if (t.id === "cu-tpl" && t.selectedIndex > 0) { const liste = modeles()[t.value] || []; (S.catalogue || []).forEach((d) => { S.draft[d.droit] = liste.indexOf(d.droit) >= 0 ? "accorde" : "herite"; }); dire("Modèle « " + t.value + " » préparé : rien n'est appliqué avant validation.", "ok"); dessiner(); }
      else if (t.id === "cu-cpy" && t.value) { S.catalogue.forEach((d) => { S.draft[d.droit] = accordDe("compte", t.value, d.droit); }); dire("Droits de " + nomDe(compteDe(t.value)) + " préparés : rien n'est appliqué avant validation.", "ok"); dessiner(); }
      else if (t.id === "nu-mod") S.nu.modele = t.value;
      else if (t.id === "qui-d") { S.droitQui = t.value; await chargerQui(); dessiner(); }
    });
    racine.addEventListener("input", (e) => {
      const t = e.target; if (t.id !== "cu-q" && t.id !== "cu-qd") return;
      if (t.id === "cu-q") S.q = t.value; else S.qd = t.value;
      const p = t.selectionStart; dessiner(); const n = $("#" + t.id); if (n) { n.focus(); n.setSelectionRange(p, p); }
    });
    // Rouvrir l'écran depuis le menu repart de sa page d'origine, avec des données fraîches (sinon la liste montrerait encore la dernière fiche ouverte)
    const initiale = S.page, onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active");
      new MutationObserver(() => { const actif = onglet.classList.contains("active"); if (actif && !etait && !S.charge) { Object.assign(S, { page: initiale, fiche: "", gfiche: "", onglet: "", draft: {}, adm: null, q: "", filtre: "tous", fl: "tous", qd: "", ouvert: null, jeton: null }); recharger(); } etait = actif; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    await charger(); S.charge = false;
    if (S.page === "qui") await chargerQui(); if (S.page === "journal") await chargerJournal();
    dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
