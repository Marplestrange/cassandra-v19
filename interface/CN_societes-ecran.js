// ══════════════════════════════════════════════════════════════════════════════
// TITRE      : L'écran Société / Organisation
// LICENCE    : AGPL-3.0
// AUTEUR     : Atek Drisse
// GIT        : github.com/Marplestrange
// MAIL       : marplestrange@cassandra.center
// MODULE     : interface
// ZONE       : CN
// VERSION CN : 0.1.0  #f537ec
// VERSION EC : néant
// EC LIÉES   : néant
// RÔLE       : L'écran de la fiche société : identité, établissements, horaires, présence, responsables, fonctions, pièces, banque, conformité, habillage, coffre, multi-sociétés, historique.
// MÉTHODE    : une scène (CASS.sceneSurMesure.societes) ; la page vient de l'écran ouvert (s_identite, s_etabs…). Chaque champ s'enregistre à la validation et passe par une capacité du module Sociétés.
// ══════════════════════════════════════════════════════════════════════════════
// ▼▼▼ BORNE CN version=0.1.0 empreinte=f537ec ▼▼▼
(function () {
  "use strict";
  const CASS = window.CASS, K = CASS.kit, esc = K.esc, agir = K.agir, dire = K.dire, confirmer = K.confirmer;
  const PAGES = { vue_societe: "identite", s_identite: "identite", s_etabs: "etabs", s_horaires: "horaires", s_presence: "presence", s_equipe: "equipe", s_fonctions: "fonctions", s_pieces: "pieces",
    s_banque: "banque", s_conformite: "conformite", s_habillage: "habillage", s_coffre: "coffre", s_modules: "modules", s_partages: "partages", s_carnet: "carnet", s_reglages: "reglages", s_sert: "sert", s_multi: "multi", s_histo: "histo" };
  const JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
  const DOMAINES = [["fiche", "Fiche société", 0], ["etablissements", "Établissements", 0], ["horaires", "Horaires et calendrier", 0], ["pieces", "Pièces et échéances", 0], ["banque", "Banque et facturation", 1],
    ["conformite", "Conformité", 0], ["habillage", "Habillage et modèles", 0], ["equipe", "Fonctions et responsables", 1]];
  const NIV = ["Aucun", "Voir", "Modifier", "Gérer"];
  const FUSEAUX = ["", "Europe/Paris", "Europe/Zurich", "Europe/Brussels", "Europe/London", "America/Toronto"];
  const DEVISES = ["", "EUR", "CHF", "CAD", "USD", "GBP"];
  const FORMES = ["", "SAS", "SARL", "SA", "EURL", "SCI", "Association", "Auto-entrepreneur", "Sàrl", "Autre"];
  const PAYS = ["", "France", "Suisse", "Belgique", "Luxembourg", "Canada"];
  const LANGUES = ["", "Français", "English", "Deutsch", "Italiano"];
  const COULEURS = ["#0b7c74", "#2f5fd0", "#7a3fc4", "#b4530b", "#be123c", "#3d4a57"];
  const ENTETES = [["classique", "Classique", "Logo à gauche, filet de couleur"], ["sobre", "Sobre", "Texte seul, sans filet"], ["bandeau", "Bandeau", "Aplat de couleur en haut"]];
  const ROLES = [["titulaire", "Titulaire", "Représente la société dans l’instance ; reçoit les alertes graves."], ["legal", "Représentant légal", "Signe les mentions légales et les contrats."],
    ["dpo", "Délégué à la protection des données", "Reçoit les demandes RGPD (accès, effacement)."], ["facturation", "Contact facturation", "Reçoit les factures et les relances."],
    ["securite", "Contact sécurité", "Reçoit les alertes du Sensorium et des sauvegardes."]];
  const CONF = [["mentions", "Mentions légales", "Générées depuis la fiche (raison sociale, SIREN, capital, siège, hébergeur)."], ["rgpd", "Registre des traitements", "Un traitement par module qui garde des données personnelles."],
    ["dpo", "Délégué désigné", "Nécessaire si vous traitez des données à grande échelle."], ["cgv", "Conditions générales", "Propres à votre activité."], ["cookies", "Bandeau cookies", "Appliqué aux sites qui utilisent le thème Cassandra."]];
  const RC = { admin: "Administrateur du coffre", membre: "Membre (lit et écrit tout)", contrib: "Contributeur (ses propres secrets seulement)", lecture: "Lecture seule" };
  const CONSOMMATEURS = [["Courrier", "signature, adresse d’expédition, pied de message"], ["Agenda", "fuseau, heures d’ouverture, jours fériés"], ["Billetterie", "titulaire, SIRET, TVA, établissements"],
    ["Documents", "en-tête, mentions légales, devise"], ["Sites", "domaines, mentions légales, cookies"], ["Notifications", "fuseau, heures d’ouverture, responsables"], ["Itare", "nom, activité, horaires : le contexte de ses réponses"]];
  const FERIES = [["01-01", "Jour de l’an"], ["05-01", "Fête du travail"], ["05-08", "Victoire 1945"], ["07-14", "Fête nationale"], ["08-15", "Assomption"], ["11-01", "Toussaint"], ["11-11", "Armistice"], ["12-25", "Noël"]];
  const CSS = ".sh-scene:has(>.sh-corps>.so){width:100%}.so{display:grid;gap:14px;color:var(--txt);font:13.5px/1.45 'Inter',system-ui,sans-serif}.so *{box-sizing:border-box}.so button{font:inherit;color:inherit;cursor:pointer}.so>*{min-width:0}" +
    ".so .i{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;flex:none}" +
    ".so .carte{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px;min-width:0}.so .carte h2{margin:0 0 3px;font-size:15px;display:flex;gap:8px;align-items:center}.so .carte h3{margin:0 0 8px;font-size:13px}" +
    ".so .sub{color:var(--txt-faint);font-size:12px;margin:0 0 12px}.so .g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.so .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.so .row .sp{flex:1}" +
    ".so .f{display:block;font:600 10.5px 'JetBrains Mono',monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--txt-faint);margin:0 0 4px}" +
    ".so input[type=text],.so input[type=email],.so input[type=url],.so input[type=tel],.so input[type=date],.so input[type=time],.so select,.so textarea{font:inherit;color:var(--txt);background:var(--surface-solid,var(--surface));border:1px solid var(--line-strong,var(--line));border-radius:10px;padding:7px 10px;width:100%;min-width:0}" +
    ".so input.bad{outline:2px solid var(--danger)}.so input[disabled],.so select[disabled]{opacity:.55}.so .hint{font-size:11.5px;color:var(--txt-faint);margin-top:3px}.so .hint.ko{color:var(--danger)}.so .hint.ok{color:var(--ok)}" +
    ".so .btn{border:1px solid var(--line-strong,var(--line));background:var(--surface-solid,var(--surface));border-radius:10px;padding:6px 12px;font-weight:600;font-size:12.5px;display:inline-flex;gap:6px;align-items:center}.so .btn:hover{border-color:var(--accent)}" +
    ".so .btn.pri{background:var(--accent);color:var(--on-accent,#fff);border-color:transparent}.so .btn.sm{padding:3px 9px;font-size:12px}.so .btn.dng{color:var(--danger)}.so .btn[disabled]{opacity:.45;pointer-events:none}" +
    ".so .chip{display:inline-flex;gap:5px;align-items:center;font-size:11px;font-weight:600;border-radius:99px;padding:2px 9px;background:var(--surface);color:var(--txt-soft);border:1px solid var(--line);white-space:nowrap}" +
    ".so .chip.ok{background:color-mix(in srgb,var(--ok) 13%,transparent);color:var(--ok);border-color:transparent}.so .chip.warn{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn);border-color:transparent}" +
    ".so .chip.acc{background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent);border-color:transparent}.so .chip.dng{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger);border-color:transparent}" +
    ".so .cols{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;align-items:start}.so .cols>*{min-width:0}.so .main{display:grid;gap:14px;min-width:0}.so .main>*{min-width:0}" +
    ".so .top{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.so .top .sp{flex:1}.so .mono-av{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font:700 12px 'JetBrains Mono',monospace;color:#fff;flex:none}" +
    ".so .tg{position:relative;width:38px;height:22px;border-radius:99px;background:var(--line-strong,var(--line));border:0;flex:none;padding:0}.so .tg:after{content:'';position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:left .15s}.so .tg.on{background:var(--accent)}.so .tg.on:after{left:19px}.so .tg[disabled]{opacity:.45;pointer-events:none}" +
    ".so .ring{width:46px;height:46px;border-radius:50%;display:grid;place-items:center;flex:none}.so .ring b{width:36px;height:36px;border-radius:50%;background:var(--surface);display:grid;place-items:center;font:600 11.5px 'JetBrains Mono',monospace}" +
    ".so .tw{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface)}.so table{border-collapse:collapse;width:100%;font-size:13px}.so th{font:600 10.5px 'JetBrains Mono',monospace;letter-spacing:.07em;text-transform:uppercase;color:var(--txt-faint);text-align:left;padding:9px 12px;white-space:nowrap}.so td{padding:8px 12px;border-top:1px solid var(--line);vertical-align:middle}" +
    ".so .etab{border:1px solid var(--line);border-radius:12px;padding:11px 12px;background:var(--surface);display:grid;gap:7px}.so .etab.sel{border-color:var(--accent)}.so .list{display:grid;gap:8px}.so .cap{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}.so .cap div{border:1px solid var(--line);border-radius:12px;padding:9px 12px;background:var(--surface)}.so .cap small{display:block;color:var(--txt-faint)}" +
    ".so .ev{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--line)}.so .ev:first-child{border-top:0}.so .ev time{font:500 11.5px 'JetBrains Mono',monospace;color:var(--txt-faint)}" +
    ".so .pvtabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:10px}.so .pvtabs button{border:0;background:none;padding:6px 10px;color:var(--txt-soft);border-bottom:2px solid transparent;font-weight:500}.so .pvtabs button.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:650}" +
    ".so .paper{background:#fff;color:#1b2430;border-radius:8px;border:1px solid #d9e0e6;padding:16px;font-size:11.5px;line-height:1.4;min-height:190px}.so .paper .hd{display:flex;gap:10px;align-items:center;border-bottom:2px solid var(--pa,#0b7c74);padding-bottom:8px;margin-bottom:10px}.so .paper .hd b{font-size:13px;display:block}.so .paper small{color:#6a7784}.so .paper .ft{margin-top:18px;border-top:1px solid #e4e9ee;padding-top:6px;color:#6a7784;font-size:10px}" +
    ".so .login{background:linear-gradient(135deg,var(--pa,#0b7c74),#10202a);color:#fff;border-radius:10px;padding:22px 16px;text-align:center;min-height:190px;display:grid;place-content:center;gap:8px}.so .login .mono-av{margin:0 auto;width:46px;height:46px;font-size:16px;background:rgba(255,255,255,.2)!important}.so .login .fk{background:rgba(255,255,255,.14);border-radius:8px;padding:7px;font-size:11px}" +
    ".so .colors{display:flex;gap:8px;flex-wrap:wrap}.so .colors button{width:30px;height:30px;border-radius:50%;border:2px solid transparent;outline:1px solid var(--line-strong,var(--line))}.so .colors button.on{border-color:var(--surface);outline:2px solid var(--txt)}" +
    ".so .sug{display:flex;gap:10px;align-items:center;flex-wrap:wrap;border:1px dashed var(--accent);background:color-mix(in srgb,var(--accent) 9%,transparent);border-radius:12px;padding:8px 12px}.so .note{border:1px dashed var(--line-strong,var(--line));border-radius:12px;padding:9px 12px;font-size:12.5px;color:var(--txt-soft)}" +
    ".so .wk .d{display:grid;grid-template-columns:90px 38px minmax(0,1fr);gap:10px;align-items:center;padding:6px 0;border-top:1px solid var(--line)}.so .wk .d:first-child{border-top:0}.so .wk .hrs{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.so .wk .hrs input{width:100px}" +
    ".so .vide{color:var(--txt-faint);padding:14px 0}.so .herit{display:inline-flex;gap:6px;align-items:center;font-size:11px;color:var(--info,var(--accent));margin-left:6px}.so .mx select{min-width:98px}" +
    "@media (max-width:980px){.so .cols{grid-template-columns:1fr}}";
  const IC = { id: '<path d="M3 7h18v12H3z"/><path d="M7 11h4M7 15h7"/><circle cx="16.5" cy="11.5" r="1.5"/>', pin: '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>', users: '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6"/><path d="M16 5a3 3 0 0 1 0 6M18 14c2 .8 3 2.8 3 6"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>', file: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>', bank: '<path d="M3 10l9-6 9 6"/><path d="M5 10v8M10 10v8M14 10v8M19 10v8M3 20h18"/>',
    brush: '<path d="M4 20c3 0 5-1 5-3.5L19 5l-2-2L7.5 13C5 13 4 15 4 17z"/>', plus: '<path d="M12 5v14M5 12h14"/>', down: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>', lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>', spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>' };
  const ic = (n) => '<svg class="i" viewBox="0 0 24 24">' + (IC[n] || "") + "</svg>";

  // ── règles côté écran (le serveur revalide tout) ─────────────────────────
  const luhn = (n) => { n = String(n).replace(/\s/g, ""); if (!/^\d{9}$/.test(n)) return false; let s = 0; for (let i = 0; i < 9; i++) { let d = +n[8 - i]; if (i % 2 === 1) { d *= 2; if (d > 9) d -= 9; } s += d; } return s % 10 === 0; };
  const tva = (siren) => { if (!luhn(siren)) return ""; const s = String(siren).replace(/\s/g, ""); return "FR" + ("0" + ((12 + 3 * (parseInt(s, 10) % 97)) % 97)).slice(-2) + s; };
  const monogramme = (nom) => (String(nom || "?").split(/\s+/).filter(Boolean).map((w) => w[0]).join("").slice(0, 2).toUpperCase()) || "?";
  const contraste = (hex) => { const c = String(hex || "#0b7c74").replace("#", ""); const r = [0, 2, 4].map((i) => { const v = parseInt(c.substr(i, 2), 16) / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); const L = 0.2126 * r[0] + 0.7152 * r[1] + 0.0722 * r[2]; return Math.round(1.05 / (L + 0.05) * 10) / 10; };
  const jours = (d) => { const t = new Date(); t.setHours(0, 0, 0, 0); return Math.round((new Date(d + "T00:00:00") - t) / 864e5); };
  const chip = (t, c) => '<span class="chip ' + (c || "") + '">' + esc(t) + "</span>";
  const chipJ = (j) => chip(j < 0 ? "échu" : j === 0 ? "aujourd’hui" : "dans " + j + " j", j < 0 ? "dng" : j <= 30 ? "warn" : "ok");

  CASS.sceneSurMesure = CASS.sceneSurMesure || {};
  CASS.sceneSurMesure.societes = async function (corps, ctx) {
    K.injecter();
    if (!document.getElementById("so-css")) { const st = document.createElement("style"); st.id = "so-css"; st.textContent = CSS; document.head.appendChild(st); }
    corps.innerHTML = ""; const racine = document.createElement("div"); racine.className = "so"; corps.appendChild(racine);
    const S = { page: PAGES[String(ctx && ctx.ecran || "").split(":")[1]] || "identite", liste: [], multi: false, superadmin: false, actif: "", fiche: { rubriques: {}, acces: {} }, fonc: null, membres: [], hist: [], ech: [], espaces: [],
      cof: "soc", cofMembres: null, cofSecrets: null, pv: "entete", menu: false, sim: { jour: 1, heure: 10 }, erreur: "", charge: true, comptes: [] };
    const $ = (s) => racine.querySelector(s);
    const lire = async (cap, args) => { try { return await agir(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } };
    const geste = async (cap, args, ok) => { try { const r = await agir(cap, args); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(e.message || String(e), "err"); return false; } };
    const soc = () => S.liste.find((x) => x.id === S.actif) || S.liste[0] || { id: S.actif, nom: "", principale: true };
    const R = (r) => S.fiche.rubriques[r] || {};
    const niv = (d) => S.fiche.acces[d] || 0;
    const peut = (d, n) => niv(d) >= n;
    const nomSoc = () => (R("identite").nom || soc().nom || "");
    const lecture = (d) => '<div class="carte"><div class="vide">Votre fonction dans cette société ne vous ouvre pas cette rubrique. Demandez-la à son administrateur.</div></div>';

    // ── chargement ───────────────────────────────────────────────────────
    async function chargerBase() {
      const l = await lire("societes.lister");
      if (l) { S.liste = l.societes || []; S.multi = !!l.multi; S.superadmin = !!l.superadmin; if (!S.actif) { const m = CASS.societe || ""; S.actif = S.liste.some((x) => x.id === m) ? m : (l.societe || (S.liste[0] || {}).id || "1"); } }
      if (!S.liste.some((x) => x.id === S.actif)) S.actif = (S.liste[0] || {}).id || "1";
    }
    async function chargerFiche() { const f = await lire("societes.fiche_lire", { societe: S.actif }); S.fiche = f ? { rubriques: f.rubriques || {}, acces: f.acces || {} } : { rubriques: {}, acces: {} }; }
    async function chargerPage() {
      S.erreur = "";
      const p = S.page;
      if (p === "fonctions") { const [f, m] = await Promise.all([lire("societes.fonctions", { societe: S.actif }), lire("societes.membres", { societe: S.actif })]); S.fonc = f; S.membres = (m && m.membres) || []; }
      if (p === "equipe") { const m = await lire("societes.membres", { societe: S.actif }); S.membres = (m && m.membres) || []; }
      if (p === "modules") {
        const m = await lire("societes.modules", { societe: S.actif }); S.mods = (m && m.modules) || []; S.modsPeut = !!(m && m.peut_regler);
        const dm = await lire("societes.module_demandes", S.superadmin ? { toutes: true } : { societe: S.actif }); S.demandes = (dm && dm.demandes) || []; S.peutDecider = !!(dm && dm.peut_decider);
      }
      if (p === "carnet") {
        S.erreurCarnet = "";
        let c = null; try { c = await agirSoc("contacts.societe_lister", { limite: 500 }); } catch (e) { S.erreurCarnet = /n'est pas ouvert/.test(e.message || "") ? "Le module Carnet d’adresses n’est pas ouvert dans cette société : ouvrez-le dans « Modules »." : (e.message || String(e)); }
        S.carnet = (c && c.contacts) || [];
        const pt = await lire("societes.partages", { societe: S.actif });
        const src = ((pt && pt.entrants) || []).filter((x) => x.type === "contacts");
        S.carnetDist = [];
        for (const x of src) { try { const r = await agirSoc("contacts.societe_partage_lister", { depuis: x.source, limite: 500 }); S.carnetDist.push({ source: x.source, contacts: (r && r.contacts) || [] }); } catch (e) { /* un partage retiré entre-temps */ } }
      }
      if (p === "partages") {
        const [pt, pb, f, m] = await Promise.all([lire("societes.partages", { societe: S.actif }), peut("equipe", 3) ? lire("societes.partageables", { societe: S.actif }) : null, peut("equipe", 3) ? lire("societes.fonctions", { societe: S.actif }) : null, lire("societes.membres", { societe: S.actif })]);
        S.part = pt || { sortants: [], entrants: [] }; S.partageables = (pb && pb.utilisateurs) || []; S.fonc = f || S.fonc; S.membres = (m && m.membres) || [];
      }
      if (p === "reglages") { const r = await lire("reglages.lire", { pour_societe: S.actif }); S.regl = ((r && r.reglages) || []).filter((x) => x.portee === "societe"); }
      if (p === "pieces") { const e = await lire("societes.echeances", { societe: S.actif }); S.ech = (e && e.echeances) || []; }
      if (p === "histo") { const h = await lire("societes.historique", { societe: S.actif, limite: 100 }); S.hist = (h && h.historique) || []; }
      if (p === "coffre") { const m = await lire("societes.membres", { societe: S.actif }); S.membres = (m && m.membres) || []; S.erreur = ""; await chargerCoffre(); }
      if (p === "multi") { const l = await lire("societes.lister"); if (l) { S.liste = l.societes || []; S.multi = !!l.multi; } }
    }
    async function chargerCoffre() {
      const e = await lire("coffre.espaces"); S.espaces = (e && e.espaces) || []; S.cofMembres = null; S.cofSecrets = null;
      const mon = S.espaces.find((x) => x.id === "s:" + S.actif);
      if (mon && S.cof === "soc") {
        const m = await lire("coffre.membres", { espace: mon.id }); S.cofMembres = m;
        const l = await lire("coffre.list", { espace: mon.id }); S.cofSecrets = l;
      }
    }
    async function recharger() { await chargerFiche(); await chargerPage(); dessiner(); }
    async function choisir(id) { S.actif = id; S.menu = false; await recharger(); }      // la société qu'on ADMINISTRE ici ; le sélecteur de l'en-tête, lui, change toute l\'application

    // ── complétude ───────────────────────────────────────────────────────
    const CHAMPS = [["identite", "nom", "Raison sociale", 2], ["identite", "forme", "Forme juridique", 1], ["identite", "siren", "SIREN valide", 2], ["siege", "adresse", "Adresse du siège", 2], ["siege", "ville", "Ville", 1], ["siege", "email", "Courriel de contact", 2],
      ["siege", "tel", "Téléphone", 1], ["regional", "fuseau", "Fuseau horaire", 2], ["siege", "web", "Site web", 1], ["identite", "capital", "Capital", 1]];
    function completude() { let tot = 0, ok = 0; const manque = []; CHAMPS.forEach((c) => { tot += c[3]; const v = (R(c[0]) || {})[c[1]]; const bon = c[1] === "siren" ? luhn(v) : !!String(v || "").trim(); if (bon) ok += c[3]; else manque.push(c[2]); }); return { pct: tot ? Math.round(100 * ok / tot) : 0, manque: manque }; }

    // ── pièces communes ──────────────────────────────────────────────────
    const champ = (rub, k, lib, type, opt) => {
      opt = opt || {}; const v = (R(rub) || {})[k] || ""; const ro = !peut(opt.dom || "fiche", 2);
      const id = "c-" + rub + "-" + k;
      const ctl = type === "select" ? '<select id="' + id + '" data-r="' + rub + '" data-k="' + k + '"' + (ro ? " disabled" : "") + ">" + opt.opts.map((o) => "<option" + (o === v ? " selected" : "") + ">" + esc(o) + "</option>").join("") + "</select>"
        : '<input id="' + id + '" type="' + (type || "text") + '" data-r="' + rub + '" data-k="' + k + '" value="' + esc(v) + '"' + (opt.bad ? ' class="bad"' : "") + (ro ? " disabled" : "") + ' autocomplete="off"' + (opt.ph ? ' placeholder="' + esc(opt.ph) + '"' : "") + ">";
      return '<div><label class="f" for="' + id + '">' + lib + "</label>" + ctl + (opt.hint ? '<div class="hint ' + (opt.cls || "") + '" id="h-' + k + '">' + opt.hint + "</div>" : "") + "</div>";
    };
    const nomAv = (n, a) => '<span class="mono-av" style="background:' + esc(a || R("habillage").accent || "#0b7c74") + '">' + esc(monogramme(n)) + "</span>";

    function entete() {
      const c = completude(), s = soc();
      const menu = S.menu ? '<div class="carte" style="position:absolute;z-index:20;margin-top:6px;min-width:280px;padding:6px" role="menu">' + S.liste.map((x) => '<button class="btn" style="display:flex;width:100%;border:0;justify-content:flex-start" data-a="soc" data-id="' + esc(x.id) + '">' + nomAv(x.nom, x.id === S.actif ? R("habillage").accent : "") + "<span><b>" + esc(x.nom) + "</b>" + (x.principale ? " " + chip("principale", "acc") : "") + (x.id === S.actif ? " " + chip("active", "ok") : "") + "</span></button>").join("") + "</div>" : "";
      const sel = S.liste.length > 1 ? '<div style="position:relative"><button class="btn" data-a="menu" aria-haspopup="menu" aria-expanded="' + S.menu + '">' + nomAv(s.nom) + "<span>" + esc(s.nom) + "</span></button>" + menu + "</div>" : '<div class="row">' + nomAv(s.nom) + "<b>" + esc(s.nom) + "</b></div>";
      return '<div class="carte top">' + sel + '<span class="sp"></span><div class="row" title="Part des champs utiles remplis"><div class="ring" style="background:conic-gradient(var(--accent) ' + c.pct + '%,var(--line) 0)"><b>' + c.pct + '%</b></div><span style="font-size:12px;color:var(--txt-soft)">fiche<br>complète</span></div></div>';
    }

    // ── aperçu en direct ─────────────────────────────────────────────────
    function apercu() {
      const i = R("identite"), sg = R("siege"), rg = R("regional"), h = R("habillage"), acc = h.accent || "#0b7c74", nom = i.nom || soc().nom;
      const adr = [sg.adresse, ((sg.cp || "") + " " + (sg.ville || "")).trim()].filter(Boolean).join(", ");
      const sir = luhn(i.siren) ? "SIREN " + i.siren.replace(/(\d{3})(?=\d)/g, "$1 ") + " · " + tva(i.siren) : "";
      const av = nomAv(nom, acc);
      if (S.pv === "mail") return '<div class="paper" style="--pa:' + esc(acc) + '"><div style="color:#6a7784;margin-bottom:10px">De : vous &lt;' + esc(sg.email || "") + '&gt;<br>Objet : Votre devis</div><div>Bonjour,<br>Veuillez trouver ci-joint notre proposition.</div><div style="margin-top:14px;border-left:3px solid ' + esc(acc) + ';padding-left:10px"><b>Vous</b><br>' + esc(nom) + " " + esc(i.forme || "") + (h.signature !== "courte" ? "<br><small>" + esc(adr) + "<br>" + esc(sg.tel || "") + " · " + esc(sg.web || "") + "</small>" : "") + '</div><div class="ft">' + esc(nom) + " " + esc(i.forme || "") + (i.capital ? " au capital de " + esc(i.capital) : "") + (sir ? " · " + sir : "") + "</div></div>";
      if (S.pv === "login") return '<div class="login" style="--pa:' + esc(acc) + '">' + av + '<b style="font-size:15px">' + esc(nom) + '</b><div style="opacity:.8;font-size:11px">Connexion à votre espace</div><div class="fk">adresse e-mail</div><div class="fk">mot de passe</div></div>';
      return '<div class="paper" style="--pa:' + esc(acc) + '"><div class="hd">' + av + "<div><b>" + esc(nom) + " " + esc(i.forme || "") + "</b><small>" + esc(adr) + '</small></div></div><div><b>DEVIS n° 2026-0147</b><br><small>Émis le ' + new Date().toLocaleDateString("fr-FR") + " · en " + esc(rg.devise || "—") + '</small></div><div style="margin-top:12px;height:46px;background:repeating-linear-gradient(#f1f4f7 0 8px,#fff 8px 16px);border-radius:4px"></div><div class="ft">' + esc(nom) + " " + esc(i.forme || "") + (i.capital ? " au capital de " + esc(i.capital) : "") + (sir ? "<br>" + sir : "<br><i>SIREN à renseigner</i>") + "<br>" + esc(sg.email || "") + "</div></div>";
    }
    const pvTabs = () => '<div class="pvtabs">' + [["entete", "En-tête"], ["mail", "Courriel"], ["login", "Connexion"]].map((t) => '<button data-a="pv" data-id="' + t[0] + '" class="' + (S.pv === t[0] ? "on" : "") + '">' + t[1] + "</button>").join("") + "</div>";

    // ── les pages ────────────────────────────────────────────────────────
    function pIdentite() {
      if (!peut("fiche", 1)) return lecture();
      const i = R("identite"), sg = R("siege"), c = completude();
      const sirenHint = !i.siren ? "9 chiffres. Le contrôle est local, rien n’est envoyé." : (luhn(i.siren) ? "Valide · TVA " + tva(i.siren) : "Clé de contrôle invalide : vérifiez le numéro.");
      const sugs = [];
      if (!R("regional").fuseau) sugs.push({ k: "fuseau", t: "Le fuseau horaire n’est pas défini : sans lui, les rappels et l’agenda se calent sur le serveur.", b: "Appliquer " + (sg.pays === "Suisse" ? "Europe/Zurich" : "Europe/Paris") });
      return '<div class="cols"><div class="main">' + (sugs.length && peut("fiche", 2) ? '<div class="carte">' + sugs.map((x) => '<div class="sug">' + ic("spark") + '<span style="flex:1;min-width:200px"><b>Cassandra</b> · ' + esc(x.t) + '</span><button class="btn pri sm" data-a="sug" data-k="' + x.k + '">' + esc(x.b) + "</button></div>").join("") + "</div>" : "") +
        '<section class="carte"><h2>' + ic("id") + 'Identité légale</h2><p class="sub">Ce que Cassandra et les modules utilisent partout où votre société doit être nommée.</p><div class="g2">' +
        champ("identite", "nom", "Raison sociale") + champ("identite", "forme", "Forme juridique", "select", { opts: FORMES }) + champ("identite", "siren", "SIREN", "text", { bad: i.siren && !luhn(i.siren), hint: esc(sirenHint), cls: !i.siren ? "" : (luhn(i.siren) ? "ok" : "ko") }) +
        champ("identite", "ape", "Code APE / NAF") + champ("identite", "capital", "Capital social") + champ("identite", "creation", "Date de création", "date") + "</div></section>" +
        '<section class="carte"><h2>' + ic("pin") + 'Siège et contact</h2><p class="sub">Le siège est aussi le premier établissement ; les autres se déclarent dans « Établissements ».</p><div class="g2">' +
        champ("siege", "adresse", "Adresse") + champ("siege", "cp", "Code postal") + champ("siege", "ville", "Ville") + champ("siege", "pays", "Pays", "select", { opts: PAYS }) + champ("siege", "tel", "Téléphone", "tel") + champ("siege", "email", "Courriel de contact", "email") + champ("siege", "web", "Site web", "url") + "</div></section>" +
        '<section class="carte"><h2>' + ic("globe") + 'Réglages régionaux</h2><p class="sub">Les modules les lisent au lieu de les redemander : dates, montants, rappels, notifications.</p><div class="g2">' +
        champ("regional", "devise", "Devise principale", "select", { opts: DEVISES }) + champ("regional", "langue", "Langue des documents", "select", { opts: LANGUES }) + champ("regional", "fuseau", "Fuseau horaire", "select", { opts: FUSEAUX, hint: R("regional").fuseau ? "" : "À définir." }) + "</div></section></div>" +
        '<aside class="carte"><h3>Aperçu en direct</h3>' + pvTabs() + '<div id="so-pv">' + apercu() + '</div><p class="hint">Ces trois endroits lisent la fiche. Voir « Où ça sert ».</p></aside></div>';
    }
    function pEtabs() {
      if (!peut("etablissements", 1)) return lecture();
      const it = (R("etablissements").items || []), ro = !peut("etablissements", 2);
      const sg = R("siege"), liste = it.length ? it : [{ id: "_", nom: "Siège", siege: true, adresse: [sg.adresse, ((sg.cp || "") + " " + (sg.ville || "")).trim()].filter(Boolean).join(", "), siret: "", horaires_propres: false, virtuel: true }];
      return '<div class="main"><section class="carte"><h2>' + ic("pin") + 'Établissements</h2><p class="sub">Un lieu où l’on travaille, reçoit ou vend. Chacun peut avoir ses horaires et son SIRET ; il hérite du reste de la société.</p><div class="list">' +
        liste.map((e) => '<div class="etab ' + (e.siege ? "sel" : "") + '"><div class="row"><b>' + esc(e.nom) + "</b>" + (e.siege ? chip("Siège", "acc") : "") + (e.horaires_propres ? chip("Horaires propres", "acc") : chip("Horaires de la société")) + '<span class="sp"></span>' + (ro || e.virtuel ? "" : '<button class="btn sm" data-a="etab-modif" data-id="' + esc(e.id) + '">Modifier</button>' + (e.siege ? "" : '<button class="btn sm" data-a="siege" data-id="' + esc(e.id) + '">Faire du siège</button>') + '<button class="btn sm dng" data-a="etab-suppr" data-id="' + esc(e.id) + '">Retirer</button>') + '</div><div style="font:12px \'JetBrains Mono\',monospace;color:var(--txt-soft)">' + esc(e.adresse) + (e.siret ? " · SIRET " + esc(e.siret) : "") + "</div></div>").join("") + "</div></section>" +
        (ro ? "" : '<section class="carte"><h3>Ajouter un établissement</h3><div class="g2"><div><label class="f" for="en-nom">Nom</label><input id="en-nom" type="text" placeholder="Boutique de Mérignac"></div><div><label class="f" for="en-adr">Adresse</label><input id="en-adr" type="text"></div><div><label class="f" for="en-sir">SIRET (14 chiffres)</label><input id="en-sir" type="text"></div></div><div class="row" style="margin-top:10px"><button class="btn pri" data-a="etab-add">' + ic("plus") + "Ajouter</button></div></section>") + "</div>";
    }
    function pHoraires() {
      if (!peut("horaires", 1)) return lecture();
      const h = R("horaires"), j = h.jours || [], ro = !peut("horaires", 2), sm = S.sim;
      const ouvert = (jr, hr) => { const d = j[jr]; if (!d || !d.o) return false; const t = hr * 60, a = +d.a.slice(0, 2) * 60 + +d.a.slice(3), f = +d.f.slice(0, 2) * 60 + +d.f.slice(3); return t >= a && t < f; };
      const ouv = ouvert(sm.jour, sm.heure);
      const sem = j.map((d, i) => '<div class="d"><b>' + JOURS[i] + '</b><button class="tg' + (d.o ? " on" : "") + '"' + (ro ? " disabled" : "") + ' data-a="jour" data-i="' + i + '" role="switch" aria-checked="' + d.o + '" aria-label="' + JOURS[i] + ' ouvert"></button><div class="hrs">' + (d.o ? '<input type="time" data-h="' + i + '" data-w="a" value="' + d.a + '"' + (ro ? " disabled" : "") + '><span>à</span><input type="time" data-h="' + i + '" data-w="f" value="' + d.f + '"' + (ro ? " disabled" : "") + ">" : chip("Fermé")) + "</div></div>").join("");
      return '<div class="cols"><div class="main"><section class="carte"><h2>' + ic("clock") + 'Heures d’ouverture</h2><p class="sub">Fuseau ' + esc(R("regional").fuseau || "à définir") + '. Elles servent à l’agenda, aux messages d’absence et à Itare.</p><div class="wk">' + sem + "</div></section>" +
        '<section class="carte"><h2>Fermetures exceptionnelles</h2><div class="list" style="margin-top:8px">' + ((h.exceptions || []).length ? h.exceptions.map((e, i) => '<div class="row">' + chip(e.d, "warn") + '<span style="flex:1">' + esc(e.l) + "</span>" + (ro ? "" : '<button class="btn sm dng" data-a="exc-suppr" data-i="' + i + '">Retirer</button>') + "</div>").join("") : '<div class="hint">Aucune.</div>') + "</div>" +
        (ro ? "" : '<div class="row" style="margin-top:10px"><input id="ex-d" type="date" style="max-width:160px"><input id="ex-l" type="text" placeholder="Pont de l’Ascension" style="flex:1;min-width:160px"><button class="btn pri" data-a="exc-add">' + ic("plus") + "Ajouter</button></div>") + "</section>" +
        '<section class="carte"><div class="row"><h2 style="margin:0">Jours fériés</h2><span class="sp"></span><span class="hint">Fermé ces jours-là</span><button class="tg' + (h.feries ? " on" : "") + '"' + (ro ? " disabled" : "") + ' data-a="feries" role="switch" aria-checked="' + !!h.feries + '" aria-label="Fermé les jours fériés"></button></div><div class="row" style="margin-top:10px">' + FERIES.map((f) => chip(f[0].split("-").reverse().join("/") + " · " + f[1])).join("") + '</div><p class="hint">Liste fixe de la France ; les fêtes mobiles (Pâques, Ascension, Pentecôte) viendront avec le module Calendriers.</p></section></div>' +
        '<aside class="carte"><h3>Sommes-nous ouverts ?</h3><div class="row"><select id="sm-j" style="flex:1">' + JOURS.map((x, i) => '<option value="' + i + '"' + (i === sm.jour ? " selected" : "") + ">" + x + "</option>").join("") + '</select><input id="sm-h" type="time" value="' + ("0" + sm.heure).slice(-2) + ':00" step="3600" style="width:110px"></div>' +
        '<div class="carte" style="margin-top:10px;background:color-mix(in srgb,' + (ouv ? "var(--ok)" : "var(--warn)") + ' 12%,transparent)"><b style="color:' + (ouv ? "var(--ok)" : "var(--warn)") + '">' + (ouv ? "Ouvert" : "Fermé") + '</b><div class="hint" style="margin:4px 0 0">' + JOURS[sm.jour] + " à " + sm.heure + " h</div></div></aside></div>";
    }
    function pPresence() {
      if (!peut("fiche", 1)) return lecture();
      const p = R("presence");
      return '<div class="main"><section class="carte"><h2>' + ic("globe") + 'Présence en ligne</h2><p class="sub">Identifiants des pages de la société ; Courrier et Billetterie les reprennent pour les pieds de message et les billets.</p><div class="g2">' +
        [["linkedin", "LinkedIn"], ["instagram", "Instagram"], ["facebook", "Facebook"], ["youtube", "YouTube"], ["whatsapp", "WhatsApp"]].map((r) => champ("presence", r[0], r[1], "text", { ph: "identifiant ou lien" })).join("") + "</div></section></div>";
    }
    function pEquipe() {
      if (!peut("equipe", 1)) return lecture();
      const ro = !peut("equipe", 3), r = R("roles");
      return '<div class="main"><section class="carte"><h2>' + ic("users") + 'Responsables</h2><p class="sub">Un rôle est un lien vers un compte réel : il dit qui reçoit, pas qui voit. Les droits se règlent dans « Fonctions et droits ».</p><div class="list">' +
        ROLES.map((x) => '<div class="etab"><div class="row"><b>' + x[1] + '</b><span class="sp"></span><select data-role="' + x[0] + '"' + (ro ? " disabled" : "") + ' aria-label="' + x[1] + '" style="max-width:260px"><option value="">— personne —</option>' + S.membres.map((m) => '<option value="' + esc(m.compte) + '"' + (m.compte === r[x[0]] ? " selected" : "") + ">" + esc(m.nom || m.compte) + "</option>").join("") + '</select></div><div class="hint" style="margin:0">' + x[2] + "</div>" + (r[x[0]] ? "" : '<div class="hint ko" style="margin:0">Non désigné.</div>') + "</div>").join("") + "</div></section></div>";
    }
    function pFonctions() {
      if (!peut("equipe", 1)) return lecture();
      const F = (S.fonc && S.fonc.fonctions) || [], ro = !peut("equipe", 3), pers = (id) => F.find((f) => f.fonction === id) ? F.find((f) => f.fonction === id).membres.length : 0;
      const head = "<tr><th>Domaine</th>" + F.map((f) => '<th title="' + esc(f.description) + '">' + esc(f.nom) + '<br><span style="font-weight:500;text-transform:none;letter-spacing:0">' + f.membres.length + " pers.</span></th>").join("") + "</tr>";
      const body = DOMAINES.map((d) => "<tr><td><b>" + d[1] + "</b>" + (d[2] ? " " + chip("sensible", "warn") : "") + "</td>" + F.map((f) => '<td class="mx"><select data-fc="' + esc(f.fonction) + "|" + d[0] + '" aria-label="' + esc(f.nom) + " : " + d[1] + '"' + (ro || f.fixe ? " disabled" : "") + ">" + NIV.map((n, k) => '<option value="' + k + '"' + ((f.niveaux[d[0]] || 0) === k ? " selected" : "") + ">" + n + "</option>").join("") + "</select></td>").join("") + "</tr>").join("");
      const aff = S.membres.map((m) => '<tr><td><b>' + esc(m.nom || m.compte) + '</b><br><small style="color:var(--txt-faint)">' + esc(m.compte) + '</small></td><td><select data-af="' + esc(m.compte) + '"' + (ro ? " disabled" : "") + ' aria-label="Fonction de ' + esc(m.compte) + '" style="min-width:160px"><option value="">— aucune —</option>' + F.map((f) => '<option value="' + esc(f.fonction) + '"' + (f.fonction === m.fonction ? " selected" : "") + ">" + esc(f.nom) + "</option>").join("") + "</select></td><td>" + (m.fonction ? chip("fonction active", "ok") : chip("Aucune fonction ici")) + "</td></tr>").join("");
      return '<div class="main"><section class="carte"><h2>' + ic("shield") + "Fonctions et droits de " + esc(nomSoc()) + '</h2><p class="sub">Une fonction est un niveau de responsabilité dans cette société. Chaque domaine a quatre niveaux : aucun, voir, modifier, gérer. Une fonction ne vaut que dans sa société.</p><div class="tw"><table><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>" +
        (ro ? "" : '<div class="row" style="margin-top:12px"><input id="fn-n" type="text" placeholder="Nouvelle fonction, par exemple Responsable boutique" style="flex:1;min-width:220px"><select id="fn-b" style="max-width:200px" aria-label="Partir de">' + F.map((f) => '<option value="' + esc(f.fonction) + '">Partir de : ' + esc(f.nom) + "</option>").join("") + '</select><button class="btn pri" data-a="fn-add">' + ic("plus") + "Créer la fonction</button></div>") + "</section>" +
        '<section class="carte"><h2>' + ic("users") + 'Qui a quelle fonction</h2><p class="sub">Une fonction par personne et par société ; un seul titulaire. Ses droits personnels et ceux de ses groupes s’y ajoutent ; un refus l’emporte toujours.</p><div class="tw"><table><thead><tr><th>Utilisateur</th><th>Fonction</th><th>Ici</th></tr></thead><tbody>' + (aff || '<tr><td colspan="3" class="vide">Personne dans cette société.</td></tr>') + "</tbody></table></div></section>" +
        '<section class="carte"><h3>Comment c’est construit</h3><div class="cap"><div><b>Une fonction est un groupe attaché à une société</b><small>Même moteur que les groupes d’Utilisateurs et groupes : accordé, refusé, hérité ; le refus l’emporte.</small></div><div><b>Personne ne donne plus qu’il n’a</b><small>On n’accorde qu’un niveau égal ou inférieur au sien ; « Gérer » un domaine sensible demande une confirmation.</small></div><div><b>Un titulaire, toujours</b><small>Le transfert fait de l’ancien titulaire un administrateur.</small></div></div></section></div>';
    }
    function pPieces() {
      if (!peut("pieces", 1)) return lecture();
      const it = R("pieces").items || [], ro = !peut("pieces", 2);
      return '<div class="cols"><div class="main"><section class="carte"><h2>' + ic("file") + 'Pièces légales</h2><p class="sub">Les documents qui prouvent l’existence de la société. Le fichier reste dans Documents ; ici on garde le lien et la date de fin de validité.</p><div class="list">' +
        (it.length ? it.map((p, i) => '<div class="etab"><div class="row"><b>' + esc(p.nom) + "</b>" + (p.exp ? chipJ(jours(p.exp)) : chip("Sans échéance")) + '<span class="sp"></span>' + (ro ? "" : '<button class="btn sm dng" data-a="piece-suppr" data-i="' + i + '">Retirer</button>') + '</div><div class="hint" style="margin:0">' + (p.exp ? "Valable jusqu’au " + esc(p.exp) : "Pas de date de fin") + "</div></div>").join("") : '<div class="hint">Aucune pièce pour cette société.</div>') + "</div>" +
        (ro ? "" : '<div class="row" style="margin-top:12px"><input id="pc-n" type="text" placeholder="Attestation de capacité" style="flex:1;min-width:180px"><input id="pc-d" type="date" style="max-width:160px"><button class="btn pri" data-a="piece-add">' + ic("plus") + "Ajouter</button></div>") + "</section></div>" +
        '<aside class="carte"><h3>Échéances à venir</h3>' + (S.ech.length ? S.ech.map((e) => '<div class="ev" style="grid-template-columns:minmax(0,1fr) auto"><span><b style="font-weight:600">' + esc(e.nom) + '</b><br><small style="color:var(--txt-faint)">' + esc(e.date) + "</small></span>" + chipJ(e.jours) + "</div>").join("") : '<div class="hint">Aucune échéance.</div>') + '<p class="hint">Cassandra prévient les responsables concernés avant chaque échéance.</p></aside></div>';
    }
    function pBanque() {
      if (!peut("banque", 1)) return lecture();
      const b = R("banque"), ro = !peut("banque", 3), montre = S.iban !== undefined;
      return '<div class="main"><section class="carte"><div class="row"><h2 style="margin:0">' + ic("bank") + 'Coordonnées bancaires</h2>' + chip("sensible", "warn") + '</div><p class="sub">Pour les factures et les remboursements. L’IBAN est masqué à l’écran, absent des journaux, et chaque affichage est inscrit à l’historique.</p><div class="g2">' +
        champ("banque", "banque", "Banque", "text", { dom: "banque" }) + '<div><label class="f" for="b-iban">IBAN</label><div class="row" style="flex-wrap:nowrap"><input id="b-iban" type="text" data-r="banque" data-k="iban" value="' + esc(montre ? S.iban : (b.iban || "")) + '"' + (montre && !ro ? "" : " readonly") + '><button class="btn sm" data-a="iban"' + (peut("banque", 3) ? "" : " disabled") + ">" + (montre ? "Masquer" : "Afficher") + "</button></div></div>" + champ("banque", "bic", "BIC", "text", { dom: "banque" }) + "</div></section>" +
        '<section class="carte"><h2>Numérotation et exercice</h2><p class="sub">Les modules de facturation et la billetterie numérotent et datent sans te le redemander.</p><div class="g2">' +
        champ("banque", "pref_devis", "Préfixe des devis", "text", { dom: "banque" }) + champ("banque", "pref_facture", "Préfixe des factures", "text", { dom: "banque" }) + champ("banque", "tva_taux", "Taux de TVA par défaut (%)", "text", { dom: "banque" }) +
        champ("banque", "exo_deb", "Début de l’exercice (mois-jour)", "text", { dom: "banque", ph: "01-01" }) + champ("banque", "exo_fin", "Fin de l’exercice (mois-jour)", "text", { dom: "banque", ph: "12-31", hint: "Alimente l’échéance de clôture." }) + "</div></section></div>";
    }
    function pConformite() {
      if (!peut("conformite", 1)) return lecture();
      const c = R("conformite"), ro = !peut("conformite", 2), n = CONF.filter((x) => c[x[0]]).length;
      return '<div class="main"><section class="carte"><div class="row"><h2 style="margin:0">' + ic("shield") + "Conformité</h2><span class=\"sp\"></span>" + chip(n + " / " + CONF.length, n === CONF.length ? "ok" : "warn") + '</div><p class="sub">Les pièces qui se déduisent de la fiche, et ce qu’il reste à faire.</p><div class="list">' +
        CONF.map((x) => { const ok = !!c[x[0]]; return '<div class="etab"><div class="row"><b>' + x[1] + '</b><span class="sp"></span>' + (ok ? chip("En place", "ok") : chip("À faire", "warn")) + (ro ? "" : '<button class="btn sm' + (ok ? "" : " pri") + '" data-a="conf" data-k="' + x[0] + '">' + (ok ? "Retirer" : "Marquer fait") + "</button>") + '</div><div class="hint" style="margin:0">' + x[2] + "</div></div>"; }).join("") + "</div></section></div>";
    }
    function pHabillage() {
      if (!peut("habillage", 1)) return lecture();
      const h = R("habillage"), ro = !peut("habillage", 2), acc = h.accent || "#0b7c74", ct = contraste(acc);
      return '<div class="cols"><div class="main"><section class="carte"><h2>' + ic("brush") + 'Habillage</h2><p class="sub">La couleur et le monogramme se propagent aux documents, courriels et à la page de connexion de la société.</p><label class="f">Couleur de la société</label><div class="colors">' +
        COULEURS.map((c) => '<button data-a="couleur" data-c="' + c + '"' + (ro ? " disabled" : "") + ' class="' + (acc === c ? "on" : "") + '" style="background:' + c + '" aria-label="Couleur ' + c + '"></button>').join("") + '</div><div class="row" style="margin-top:12px">' + chip(ct + " : 1", ct >= 4.5 ? "ok" : "dng") + '<span class="hint" style="margin:0">' + (ct >= 4.5 ? "Lisible en texte blanc sur cette couleur (seuil 4,5)." : "Trop clair pour du texte blanc : les boutons seront assombris.") + "</span></div></section>" +
        '<section class="carte"><h3>En-tête des documents</h3><div class="g2">' + ENTETES.map((e) => '<button class="etab' + (h.entete === e[0] ? " sel" : "") + '" data-a="entete" data-id="' + e[0] + '"' + (ro ? " disabled" : "") + ' style="text-align:left"><b>' + e[1] + '</b><span class="hint" style="margin:0">' + e[2] + "</span></button>").join("") + "</div></section>" +
        '<section class="carte"><h3>Signature des courriels</h3><div class="row"><button class="btn' + (h.signature === "complete" ? " pri" : "") + '" data-a="signature" data-id="complete"' + (ro ? " disabled" : "") + '>Complète</button><button class="btn' + (h.signature === "courte" ? " pri" : "") + '" data-a="signature" data-id="courte"' + (ro ? " disabled" : "") + ">Courte</button></div></section></div>" +
        '<aside class="carte"><h3>Aperçu</h3>' + pvTabs() + '<div id="so-pv">' + apercu() + "</div></aside></div>";
    }
    function pCoffre() {
      const perso = S.cof === "perso", mon = S.espaces.find((x) => x.id === "s:" + S.actif), pers = S.espaces.find((x) => x.genre === "perso");
      const tabs = '<div class="pvtabs"><button data-a="cof" data-id="soc" class="' + (perso ? "" : "on") + '">Coffre de ' + esc(nomSoc()) + '</button><button data-a="cof" data-id="perso" class="' + (perso ? "on" : "") + '">Mes coffres</button></div>';
      if (perso) return '<div class="main"><section class="carte"><h2>' + ic("lock") + 'Mes coffres</h2>' + tabs + '<p class="sub">Tu ne vois que les espaces dont tu es membre. Les autres n’existent pas pour toi : ni leur nom, ni le nombre de leurs secrets. Cela vaut aussi pour l’administrateur de l’instance et pour Cassandra.</p><div class="list">' +
        S.espaces.map((e) => '<div class="etab' + (e.genre === "perso" ? " sel" : "") + '"><div class="row"><b>' + esc(e.nom) + "</b> " + chip(e.genre === "perso" ? "Personnel" : "Société", e.genre === "perso" ? "" : "acc") + '<span class="sp"></span><span style="font:12px \'JetBrains Mono\',monospace;color:var(--txt-soft)">' + e.secrets + " secret" + (e.secrets > 1 ? "s" : "") + " · " + (e.genre === "perso" ? "propriétaire" : esc(RC[e.role] || e.role)) + (e.expire ? " · jusqu’au " + esc(e.expire) : "") + "</span></div></div>").join("") + "</div></section></div>";
      if (!mon) return '<div class="main"><section class="carte"><h2>' + ic("lock") + "Coffre</h2>" + tabs + '<p class="sub" style="margin-top:12px">Cette société n’a pas encore d’espace de coffre, ou vous n’en êtes pas membre.</p>' + (peut("equipe", 3) || S.superadmin ? '<button class="btn pri" data-a="cof-ouvrir">' + ic("plus") + "Ouvrir l’espace de coffre</button>" : "") + "</section></div>";
      const M = (S.cofMembres && S.cofMembres.membres) || [], admin = mon.role === "admin", nad = S.cofMembres ? S.cofMembres.admins : null, sec = (S.cofSecrets && S.cofSecrets.secrets) || [];
      const cols = {}; sec.forEach((x) => { const k = x.collection || "(sans collection)"; cols[k] = (cols[k] || 0) + 1; });
      return '<div class="cols"><div class="main"><section class="carte"><div class="row"><h2 style="margin:0">' + ic("lock") + 'Coffre</h2><span class="sp"></span>' + (nad !== null ? chip(nad < 2 ? "1 seul administrateur" : nad + " administrateurs", nad < 2 ? "warn" : "ok") : "") + "</div>" + tabs +
        '<div class="row" style="margin:12px 0 4px"><span class="f" style="margin:0">Hébergement</span><button class="btn sm' + (mon.mode !== "externe" ? " pri" : "") + '" data-a="cmode" data-id="interne"' + (admin ? "" : " disabled") + '>Interne : Vaultwarden de l’instance</button><button class="btn sm' + (mon.mode === "externe" ? " pri" : "") + '" data-a="cmode" data-id="externe"' + (admin ? "" : " disabled") + ">Externe : le coffre de la société</button></div>" +
        (mon.mode === "externe" ? '<p class="hint">La fiche garde seulement l’adresse. Le branchement d’un coffre externe n’est pas encore disponible : tant qu’il ne l’est pas, aucun secret n’y est lu ni écrit.</p>' : '<p class="hint">Une organisation dans le Vaultwarden de l’instance : le contenu reste isolé par espace.</p>') + "</section>" +
        (admin ? '<section class="carte"><h3>Qui gère ce coffre</h3><p class="sub">Un administrateur du coffre ajoute et retire les membres ; il ne lit les secrets que des collections qu’on lui ouvre. Il en faut deux au minimum.</p><div class="list">' +
          M.map((m, i) => '<div class="etab"><div class="row"><b>' + esc(m.compte) + '</b><span class="sp"></span><select data-cm="' + esc(m.compte) + '" aria-label="Rôle de ' + esc(m.compte) + '" style="max-width:260px">' + Object.keys(RC).map((k) => '<option value="' + k + '"' + (m.role === k ? " selected" : "") + ">" + RC[k] + "</option>").join("") + '</select><button class="btn sm dng" data-a="cof-retirer" data-c="' + esc(m.compte) + '">Retirer</button></div><div class="hint" style="margin:0">' + (m.role === "admin" ? "Gère les membres. Collections lisibles : " + esc(m.collections || "aucune") : "Accès : " + esc(m.collections === "*" ? "toutes les collections" : (m.collections || "aucune"))) + (m.role === "contrib" ? ". Ne voit que ses propres secrets." : "") + (m.expire ? " · expire le " + esc(m.expire) : "") + "</div></div>").join("") + "</div>" +
          '<div class="row" style="margin-top:10px">' + (S.membres.length ? '<select id="cm-n" style="max-width:240px" aria-label="Compte">' + S.membres.filter((x) => !M.some((m) => m.compte === x.compte)).map((x) => "<option value=\"" + esc(x.compte) + '">' + esc(x.nom || x.compte) + "</option>").join("") + "</select>" : '<input type="text" id="cm-n" placeholder="E-mail du compte" style="max-width:240px" aria-label="Compte">') + '<select id="cm-r" style="max-width:260px" aria-label="Rôle">' + ["membre", "contrib", "lecture", "admin"].map((k) => '<option value="' + k + '">' + RC[k] + "</option>").join("") + '</select><input id="cm-c" type="text" placeholder="Collections (* : toutes)" value="*" style="max-width:200px" aria-label="Collections"><input id="cm-e" type="date" style="max-width:150px" aria-label="Expire le (facultatif)" title="Accès temporaire : laisser vide pour un accès sans fin"><button class="btn pri" data-a="cof-accorder">' + ic("plus") + "Donner l’accès</button></div>" +
          '<p class="hint">La date est facultative : un prestataire ou un remplaçant reçoit un accès qui s’éteint seul.</p></section>' : '<section class="carte"><p class="sub" style="margin:0">Vous êtes ' + esc(RC[mon.role] || mon.role) + " dans ce coffre. Seuls ses administrateurs en gèrent les accès.</p></section>") +
        (Object.keys(cols).length ? '<section class="carte"><h3>Ce que vous voyez</h3><div class="tw"><table><thead><tr><th>Collection</th><th>Secrets</th></tr></thead><tbody>' + Object.keys(cols).map((k) => "<tr><td><b>" + esc(k) + "</b></td><td>" + cols[k] + "</td></tr>").join("") + '</tbody></table></div><p class="hint">Seuls les noms apparaissent ici, jamais les valeurs.</p></section>' : "") + "</div>" +
        '<aside class="carte"><h3>Garde-fous</h3><div class="list"><div class="etab"><b>Droits</b><div class="row">' + chip("coffre.utiliser") + chip("espace : membre", "warn") + '</div><div class="hint" style="margin:0">L’accès se donne par appartenance à l’espace, pas par un droit global.</div></div><div class="etab"><b>Départ d’un administrateur</b><div class="hint" style="margin:0">Impossible tant qu’il en resterait moins d’un : le coffre ne se perd pas.</div></div><div class="etab"><b>Journal</b><div class="hint" style="margin:0">Chaque lecture, écriture et accord est inscrit : qui, quand, sur quoi.</div></div></div></aside></div>';
    }
    function demandesHtml() {
      const D = S.demandes || [], nomEt = { demandee: ["en attente", "warn"], acceptee: ["acceptée", "ok"], refusee: ["refusée", ""] };
      const ajouter = S.superadmin && soc().principale ? "" : '<div class="row" style="margin-top:12px"><input type="text" id="dm-n" placeholder="Nom du module souhaité" style="max-width:220px" aria-label="Nom du module"><input type="text" id="dm-m" placeholder="À quoi il servira" style="flex:1;min-width:200px" aria-label="Motif"><input type="text" id="dm-s" placeholder="Où le trouver (adresse, éditeur)" style="max-width:240px" aria-label="Source"><button class="btn pri" data-a="dm-add">Demander</button></div>';
      const dispo = (S.mods || []).filter((m) => !m.vital && !m.instance);
      const lignes = D.length ? '<div class="tw"><table><thead><tr><th>Société</th><th>Module demandé</th><th>Motif</th><th>État</th><th></th></tr></thead><tbody>' + D.map((x) => "<tr><td>" + esc(x.nom_societe || x.societe) + "</td><td><b>" + esc(x.nom) + "</b>" + (x.source ? '<br><small style="color:var(--txt-faint)">' + esc(x.source) + "</small>" : "") + "</td><td>" + esc(x.motif) + "</td><td>" + chip(nomEt[x.etat][0], nomEt[x.etat][1]) + (x.module ? " " + chip(x.module) : "") + (x.reponse ? '<br><small style="color:var(--txt-faint)">' + esc(x.reponse) + "</small>" : "") + "</td><td>" +
        (S.peutDecider && x.etat === "demandee" ? '<select data-dm-mod="' + x.id + '" aria-label="Module à attribuer" style="max-width:170px"><option value="">— module installé —</option>' + dispo.map((m) => '<option value="' + esc(m.id) + '">' + esc(m.nom || m.id) + "</option>").join("") + '</select> <button class="btn pri" data-a="dm-ok" data-id="' + x.id + '">Accepter</button> <button class="btn" data-a="dm-non" data-id="' + x.id + '">Refuser</button>' : "") + "</td></tr>").join("") + "</tbody></table></div>"
        : '<div class="vide">Aucune demande.</div>';
      return '<section class="carte"><h2>' + ic("puzzle") + "Demandes de module</h2><p class=\"sub\">Une société secondaire n’installe rien elle-même : elle demande, la société principale examine le module (permissions montrées, consentement), l’installe par la logithèque puis l’attribue ici.</p>" + lignes + ajouter + "</section>";
    }
    function pModules() {
      const M = S.mods || [], nom = nomSoc();
      return '<div class="main"><section class="carte"><h2>' + ic("globe") + "Modules de " + esc(nom) + '</h2><p class="sub">Chaque société a ses modules. Les modules vitaux (comptes, droits, sociétés, coffre…) sont ouverts partout ; les autres le sont là où on les ouvre. Un module fermé disparaît des menus et refuse ses gestes pour cette société.' + (S.modsPeut ? " Une société choisit ses modules parmi ceux de l’instance ; la base de l’installation (hébergement, sécurité, agents, logithèque) reste à la société principale." : " Seul l’administrateur de la société ouvre ou ferme ses modules.") + '</p><div class="tw"><table><thead><tr><th>Module</th><th>Importance</th><th>Dans cette société</th></tr></thead><tbody>' +
        (M.length ? M.map((m) => "<tr><td><b>" + esc(m.nom || m.id) + '</b><br><small style="color:var(--txt-faint)">' + esc(m.id) + "</small></td><td>" + chip(m.importance, m.importance === "vital" ? "acc" : "") + "</td><td>" + (m.instance ? chip("société principale seulement", "warn") : m.vital ? chip("toujours ouvert", "ok") : '<button class="tg' + (m.ouvert ? " on" : "") + '"' + (S.modsPeut ? "" : " disabled") + ' data-a="mod" data-id="' + esc(m.id) + '" data-o="' + (m.ouvert ? 1 : 0) + '" role="switch" aria-checked="' + !!m.ouvert + '" aria-label="' + esc(m.nom || m.id) + ' ouvert dans cette société"></button>') + "</td></tr>").join("") : '<tr><td colspan="3" class="vide">Aucun module.</td></tr>') + "</tbody></table></div></section>" + demandesHtml() + "</div>";
    }
    // le geste part dans la société qu'on regarde ici (celle de l'en-tête peut être une autre) : l'en-tête n'est lu qu'au départ de l'appel
    const agirSoc = async (cap, args) => { const o = CASS.societe; CASS.societe = S.actif; try { return await agir(cap, args); } finally { CASS.societe = o; } };
    const lireSoc = async (cap, args) => { try { return await agirSoc(cap, args || {}); } catch (e) { S.erreur = e.message || String(e); return null; } };
    const gesteSoc = async (cap, args, ok) => { try { const r = await agirSoc(cap, args); if (ok) dire(ok, "ok"); return r || true; } catch (e) { dire(e.message || String(e), "err"); return false; } };
    function pCarnet() {
      const C = S.carnet || [], D = S.carnetDist || [], nom = nomSoc(), nomDe = (id) => ((S.liste || []).find((x) => x.id === id) || {}).nom || id;
      const ligne = (f, act) => "<tr><td><b>" + esc(f.display_name || "—") + "</b>" + (f.company ? '<br><small style="color:var(--txt-faint)">' + esc(f.company) + "</small>" : "") + "</td><td>" + esc((f.emails || []).join(", ")) + "</td><td>" + esc(f.phone || f.mobile || "") + "</td><td>" + (act ? '<button class="btn" data-a="car-del" data-id="' + esc(f.id) + '">Corbeille</button>' : "") + "</td></tr>";
      const tab = (L, act) => L.length ? '<div class="tw"><table><thead><tr><th>Nom</th><th>Adresses</th><th>Téléphone</th><th></th></tr></thead><tbody>' + L.map((f) => ligne(f, act)).join("") + "</tbody></table></div>" : '<div class="vide">Aucune fiche.</div>';
      const form = '<div class="row" style="margin-top:12px"><input type="text" id="car-n" placeholder="Nom (client, fournisseur…)" style="max-width:220px" aria-label="Nom"><input type="text" id="car-e" placeholder="Adresse e-mail" style="max-width:220px" aria-label="Adresse e-mail"><input type="text" id="car-t" placeholder="Téléphone" style="max-width:150px" aria-label="Téléphone"><input type="text" id="car-s" placeholder="Société" style="max-width:170px" aria-label="Société"><button class="btn pri" data-a="car-add">Ajouter</button></div>';
      const dist = D.map((g) => '<section class="carte"><h2>' + ic("globe") + "Carnet de " + esc(nomDe(g.source)) + '</h2><p class="sub">Partagé avec ' + esc(nom) + " en lecture seule : les notes ne sont jamais montrées.</p>" + tab(g.contacts, false) + "</section>").join("");
      return '<div class="main"><section class="carte"><h2>' + ic("users") + "Carnet de " + esc(nom) + '</h2><p class="sub">Les clients, fournisseurs et partenaires de la société, communs à ses membres. Les carnets personnels restent privés. Lire est ouvert à tous les membres ; écrire demande la fonction titulaire, administrateur ou gestionnaire.</p>' +
        (S.erreurCarnet ? '<div class="vide">' + esc(S.erreurCarnet) + "</div>" : tab(C, true) + form) + "</section>" + dist + "</div>";
    }
    function pPartages() {
      const P = S.part || { sortants: [], entrants: [] }, U = S.partageables || [], F = (S.fonc && S.fonc.fonctions) || [], ro = !peut("equipe", 3), nom = nomSoc();
      const autres = (S.liste || []).filter((x) => x.id !== S.actif && !x.archivee), nomDe = (id) => ((S.liste || []).find((x) => x.id === id) || {}).nom || id;
      const entrants = P.entrants.length ? '<div class="tw"><table><thead><tr><th>Société</th><th>Ce qu’elle partage</th></tr></thead><tbody>' + P.entrants.map((e) => "<tr><td><b>" + esc(e.nom_source || nomDe(e.source)) + "</b></td><td>" + chip(e.type === "contacts" ? "carnet de contacts" : "utilisateurs") + " " + (e.mode === "tous" ? chip("tous", "ok") : chip(e.elements.length + " choisi(s)", "warn")) + "</td></tr>").join("") + "</tbody></table></div>"
        : '<div class="vide">Aucune société ne partage rien avec ' + esc(nom) + ". Le superadministrateur décide des partages.</div>";
      const dispo = U.length ? '<div class="tw"><table><thead><tr><th>Utilisateur</th><th>Sa société</th><th>Fonction ici</th></tr></thead><tbody>' + U.map((u) => '<tr><td><b>' + esc(u.compte) + "</b></td><td>" + esc(nomDe(u.societe)) + '</td><td><select data-af="' + esc(u.compte) + '"' + (ro ? " disabled" : "") + ' aria-label="Fonction de ' + esc(u.compte) + '" style="min-width:160px"><option value="">— aucune —</option>' + F.map((f) => '<option value="' + esc(f.fonction) + '"' + (f.fonction === u.fonction ? " selected" : "") + ">" + esc(f.nom) + "</option>").join("") + "</select></td></tr>").join("") + "</tbody></table></div>"
        : (ro ? "" : '<div class="vide">Aucun utilisateur partagé à ranger pour l’instant.</div>');
      const sortants = P.sortants.length ? '<div class="tw"><table><thead><tr><th>Avec</th><th>Ce qui est partagé</th><th></th></tr></thead><tbody>' + P.sortants.map((e) => "<tr><td><b>" + esc(e.nom_destinataire || nomDe(e.destinataire)) + "</b></td><td>" + chip(e.type === "contacts" ? "carnet de contacts" : "utilisateurs") + " " + (e.mode === "tous" ? chip("tous", "ok") : chip(e.elements.join(", ") || "aucun", "warn")) + "</td><td>" + (P.peut_decider ? '<button class="btn" data-a="part-del" data-d="' + esc(e.destinataire) + '" data-ty="' + esc(e.type) + '">Retirer</button>' : "") + "</td></tr>").join("") + "</tbody></table></div>"
        : '<div class="vide">' + esc(nom) + " ne partage rien.</div>";
      const ajout = P.peut_decider && autres.length ? '<div class="row" style="margin-top:12px"><select id="pt-d" aria-label="Société destinataire" style="max-width:220px">' + autres.map((x) => '<option value="' + esc(x.id) + '">' + esc(x.nom) + "</option>").join("") + '</select><select id="pt-ty" aria-label="Ce qu’on partage" style="max-width:200px"><option value="utilisateurs">Utilisateurs</option><option value="contacts">Carnet de contacts</option></select><select id="pt-m" aria-label="Mode" style="max-width:200px"><option value="tous">Tous les utilisateurs</option><option value="choisis">Ceux que je choisis</option></select>' +
        '<select id="pt-e" multiple size="4" aria-label="Utilisateurs choisis" style="min-width:200px">' + (S.membres || []).map((m) => '<option value="' + esc(m.compte) + '">' + esc(m.nom || m.compte) + "</option>").join("") + '</select><button class="btn pri" data-a="part-add">Partager</button></div><p class="hint">En mode « choisis », sélectionnez les utilisateurs dans la liste (Ctrl pour plusieurs).</p>' : "";
      return '<div class="main"><section class="carte"><h2>' + ic("users") + "Utilisateurs partagés avec " + esc(nom) + '</h2><p class="sub">Une société peut mettre ses utilisateurs à la disposition d’une autre : l’administrateur de celle-ci leur donne alors une fonction, sans pouvoir toucher aux autres comptes de l’instance.</p>' + entrants + dispo + "</section>" +
        '<section class="carte"><h2>' + ic("globe") + "Ce que " + esc(nom) + ' partage</h2><p class="sub">Seul le superadministrateur décide d’un partage : il choisit la société, et tous les utilisateurs ou ceux qu’il désigne.</p>' + sortants + ajout + "</section></div>";
    }
    function pReglages() {
      const L = S.regl || [], ro = !peut("equipe", 3) && !S.superadmin, par = {};
      L.forEach((x) => { (par[x.module] = par[x.module] || []).push(x); });
      const champ = (x) => {
        const id = "rg-" + x.cle.replace(/[^a-z0-9]/gi, "_"), v = x.valeur === null || x.valeur === undefined ? "" : x.valeur, dis = ro ? " disabled" : "";
        if (x.type === "booleen") return '<select id="' + id + '" data-rg="' + esc(x.cle) + '" data-t="booleen"' + dis + '><option value="1"' + (v ? " selected" : "") + '>Oui</option><option value="0"' + (v ? "" : " selected") + ">Non</option></select>";
        if (x.type === "choix") return '<select id="' + id + '" data-rg="' + esc(x.cle) + '" data-t="choix"' + dis + ">" + (x.choix || []).map((c) => "<option" + (c === v ? " selected" : "") + ">" + esc(c) + "</option>").join("") + "</select>";
        if (x.type === "secret") return '<input id="' + id + '" type="password" data-rg="' + esc(x.cle) + '" data-t="secret" value="' + (v ? "***" : "") + '" placeholder="valeur secrète"' + dis + ' autocomplete="new-password">';
        return '<input id="' + id + '" type="' + (x.type === "entier" ? "number" : "text") + '" data-rg="' + esc(x.cle) + '" data-t="' + x.type + '" value="' + esc(v) + '"' + dis + ' autocomplete="off">';
      };
      const cartes = Object.keys(par).sort().map((m) => '<section class="carte"><h3>' + esc(m) + '</h3><div class="list">' + par[m].map((x) => '<div class="etab"><div class="row"><label class="f" for="rg-' + esc(x.cle.replace(/[^a-z0-9]/gi, "_")) + '" style="margin:0">' + esc(x.libelle) + '</label><span class="sp"></span>' + (x.pose ? chip("propre à la société", "acc") : chip("valeur de l’instance")) + (x.pose && !ro ? '<button class="btn sm" data-a="rg-reset" data-k="' + esc(x.cle) + '">Reprendre celle de l’instance</button>' : "") + "</div>" + champ(x) + (x.aide ? '<div class="hint" style="margin:0">' + esc(x.aide) + "</div>" : "") + "</div>").join("") + "</div></section>").join("");
      return '<div class="main"><section class="carte"><h2>' + ic("globe") + "Réglages de " + esc(nomSoc()) + '</h2><p class="sub">Les réglages qui peuvent différer d’une société à l’autre (personas des agents, identité de la billetterie, adresse du progiciel…). Tant qu’une société n’a rien posé, elle suit la valeur de l’instance ; ce qu’elle pose ne change rien pour les autres.' + (ro ? " Seul l’administrateur de la société les modifie." : "") + "</p></section>" + (cartes || '<div class="carte"><div class="vide">Aucun réglage par société dans les modules ouverts.</div></div>') + "</div>";
    }
    function pSert() {
      return '<div class="main"><section class="carte"><h2>' + ic("globe") + 'Où ça sert</h2><p class="sub">Chaque module qui a besoin de nommer la société lit « societes.carte » : jamais la banque, jamais les responsables. Les modules ci-dessous sont ceux à brancher ; aucun n’est encore relié.</p><div class="tw"><table><thead><tr><th>Module</th><th>Ce qu’il lira</th><th>État</th></tr></thead><tbody>' +
        CONSOMMATEURS.map((c) => "<tr><td><b>" + c[0] + "</b></td><td>" + c[1] + "</td><td>" + chip("à brancher", "warn") + "</td></tr>").join("") + "</tbody></table></div></section>" +
        '<section class="carte"><h3>Ce que le noyau garantit</h3><div class="cap"><div><b>Une seule source</b><small>La fiche est lue, jamais recopiée : changer la raison sociale la change partout.</small></div><div><b>Droits par domaine</b><small>Modifier la fiche demande le niveau « modifier » du domaine ; la banque demande « gérer ».</small></div><div><b>Défaire</b><small>Chaque changement se défait depuis l’historique.</small></div></div></section></div>';
    }
    function pMulti() {
      const sup = S.superadmin;
      if (!S.multi) return '<div class="main"><section class="carte"><div class="row"><h2 style="margin:0">' + ic("pin") + 'Multi-sociétés</h2>' + chip("Module · App Store", "info") + '</div><p class="sub">Gérer plusieurs sociétés dans la même instance : un groupe, des filiales, des activités séparées.</p><div class="note"><b>Non activé.</b> Cette instance gère une société. Tout est déjà prêt pour en accueillir d’autres : chaque compte appartient à une société, chaque fonction est attachée à une société, chaque société a son espace de coffre.' +
        (sup ? '<div class="row" style="margin-top:10px"><button class="btn pri" data-a="multi-on">Activer plusieurs sociétés</button><span class="hint">Réservé au superadministrateur. Le module Multi-sociétés de l’App Store ajoutera le sélecteur dans chaque écran, l’héritage du groupe et la vue consolidée.</span></div>' : '<p class="hint">Seul le superadministrateur peut l’activer.</p>') + "</div></section></div>";
      return '<div class="main"><section class="carte"><div class="row"><h2 style="margin:0">' + ic("pin") + 'Sociétés de l’instance</h2>' + chip("Activé", "ok") + '<span class="sp"></span>' + (sup ? '<button class="btn sm" data-a="multi-off">Revenir à une société</button>' : "") + "</div><p class=\"sub\">Seul le superadministrateur crée, archive et administre l’ensemble des sociétés ; l’administrateur d’une société ne gère que la sienne.</p>" +
        '<div class="tw"><table><thead><tr><th>Société</th><th>État</th><th></th></tr></thead><tbody>' + S.liste.map((x) => "<tr><td><div class=\"row\">" + nomAv(x.nom, x.id === S.actif ? R("habillage").accent : "") + "<span><b>" + esc(x.nom) + "</b> " + (x.principale ? chip("principale", "acc") : "") + '<br><small style="color:var(--txt-faint)">' + esc(x.id) + "</small></span></div></td><td>" + (x.archivee ? chip("archivée", "dng") : chip("active", "ok")) + '</td><td class="row">' + (x.archivee ? "" : '<button class="btn sm" data-a="soc" data-id="' + esc(x.id) + '" data-go="1">Ouvrir</button>') + (sup && !x.principale ? (x.archivee ? '<button class="btn sm" data-a="rouvrir" data-id="' + esc(x.id) + '">Rouvrir</button>' : '<button class="btn sm dng" data-a="archiver" data-id="' + esc(x.id) + '">Archiver</button>') : "") + "</td></tr>").join("") + "</tbody></table></div>" +
        (sup ? '<div class="row" style="margin-top:12px"><input id="sc-n" type="text" placeholder="Nom de la nouvelle société" style="flex:1;min-width:220px"><input id="sc-a" type="text" placeholder="Administrateur (e-mail d’un compte)" style="flex:1;min-width:220px"><label class="hint" style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="sc-m" style="width:auto"> Reprendre les modules de la société principale</label><button class="btn pri" data-a="soc-add">' + ic("plus") + "Créer la société</button></div><p class=\"hint\">La société reçoit ses sept fonctions et son espace de coffre ; l’administrateur désigné en est le premier administrateur.</p>" : "") + "</section></div>";
    }
    function pHisto() {
      return '<div class="main"><section class="carte"><h2>' + ic("clock") + 'Historique</h2><p class="sub">Chaque changement de la fiche : qui, quand, et le geste pour le défaire quand c’est possible.</p><div class="row" style="margin-bottom:8px"><button class="btn" data-a="exporter">' + ic("down") + 'Exporter la fiche</button><label class="btn" for="so-imp" style="cursor:pointer">Importer une fiche</label><input type="file" id="so-imp" accept="application/json,.json" hidden><span class="hint">Pour dupliquer une société ou sauvegarder l’identité. Ni l’IBAN ni les responsables n’y figurent.</span></div>' +
        (S.hist.length ? S.hist.map((e) => '<div class="ev"><time>' + new Date(e.ts * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) + "</time><span>" + chip(e.qui || "système", e.qui ? "" : "acc") + " " + esc(e.resume) + (e.rubrique ? " " + chip(e.rubrique) : "") + "</span>" + (e.rubrique && e.rubrique !== "banque" && e.rubrique !== "roles" && /^a modifié/.test(e.resume) && peut("fiche", 2) ? '<button class="btn sm" data-a="defaire" data-id="' + e.id + '">Défaire</button>' : "<span></span>") + "</div>").join("") : '<div class="vide">Rien pour l’instant. Modifiez un champ de l’identité : il apparaît ici.</div>') + "</section></div>";
    }
    const PAGE = { identite: pIdentite, etabs: pEtabs, horaires: pHoraires, presence: pPresence, equipe: pEquipe, fonctions: pFonctions, pieces: pPieces, banque: pBanque, conformite: pConformite, habillage: pHabillage, coffre: pCoffre, modules: pModules, partages: pPartages, carnet: pCarnet, reglages: pReglages, sert: pSert, multi: pMulti, histo: pHisto };
    function dessiner() {
      racine.innerHTML = entete() + (S.erreur ? '<div class="carte"><span style="color:var(--danger)">' + esc(S.erreur) + "</span></div>" : "") + (S.charge ? '<div class="carte"><div class="vide">Chargement…</div></div>' : PAGE[S.page]());
    }

    function majLegere() {
      const top = $(".carte.top"); if (top) { const tmp = document.createElement("div"); tmp.innerHTML = entete(); top.replaceWith(tmp.firstChild); }
      const pv = $("#so-pv"); if (pv) pv.innerHTML = apercu();
    }
    // ── gestes ───────────────────────────────────────────────────────────
    const regler = async (rub, valeurs, ok) => { const r = await geste("societes.fiche_regler", { societe: S.actif, rubrique: rub, valeurs: valeurs }, ok); if (r) { await chargerFiche(); if (rub === "identite" && valeurs.nom) { const l = await lire("societes.lister"); if (l) S.liste = l.societes || []; } } return !!r; };
    racine.addEventListener("click", async (e) => {
      const a = e.target.closest("[data-a]"); if (!a) { if (S.menu && !e.target.closest("[data-a]")) { S.menu = false; dessiner(); } return; }
      const k = a.dataset.a, i = +a.dataset.i, id = a.dataset.id, val = (s) => (($(s) || {}).value || "").trim();
      if (k === "menu") { S.menu = !S.menu; dessiner(); }
      else if (k === "soc") { await choisir(id); }
      else if (k === "pv") { S.pv = id; dessiner(); }
      else if (k === "sug") { await regler("regional", { fuseau: (R("siege").pays === "Suisse") ? "Europe/Zurich" : "Europe/Paris" }, "Fuseau renseigné. C’est dans l’historique, avec son bouton Défaire."); dessiner(); }
      else if (k === "jour") { const j = (R("horaires").jours || []).map((x) => Object.assign({}, x)); j[i].o = !j[i].o; await regler("horaires", { jours: j }); dessiner(); }
      else if (k === "feries") { await regler("horaires", { feries: !R("horaires").feries }); dessiner(); }
      else if (k === "exc-add") { const d = val("#ex-d"), l = val("#ex-l"); if (!d || !l) { dire("Une date et un motif.", "err"); return; } await regler("horaires", { exceptions: (R("horaires").exceptions || []).concat([{ d: d, l: l }]) }); dessiner(); }
      else if (k === "exc-suppr") { const x = (R("horaires").exceptions || []).slice(); x.splice(i, 1); await regler("horaires", { exceptions: x }); dessiner(); }
      else if (k === "etab-add") { const n = val("#en-nom"), ad = val("#en-adr"), si = val("#en-sir").replace(/\s/g, ""); if (!n || !ad) { dire("Un nom et une adresse.", "err"); return; } const it = (R("etablissements").items || []).slice(); it.push({ id: "e" + Date.now(), nom: n, siege: !it.length, adresse: ad, siret: si, horaires_propres: false }); if (await regler("etablissements", { items: it }, "Établissement ajouté.")) dessiner(); }
      else if (k === "etab-modif") {
        const x = (R("etablissements").items || []).find((y) => y.id === id); if (!x) return;
        const r = await saisie("Modifier l’établissement", '<div style="display:grid;gap:10px"><label>Nom<input type="text" id="em-n" value="' + esc(x.nom) + '"></label><label>Adresse<input type="text" id="em-a" value="' + esc(x.adresse) + '"></label><label>SIRET (14 chiffres)<input type="text" id="em-s" value="' + esc(x.siret || "") + '"></label><label>Horaires<select id="em-h"><option value="0"' + (x.horaires_propres ? "" : " selected") + '>Ceux de la société</option><option value="1"' + (x.horaires_propres ? " selected" : "") + '>Propres à cet établissement</option></select></label></div>', "Enregistrer", ["em-n", "em-a", "em-s", "em-h"]);
        if (!r) return;
        const horaires = r["em-h"] === "1";
        if (!(r["em-n"] || "").trim() || !(r["em-a"] || "").trim()) { dire("Un nom et une adresse.", "err"); return; }
        const it = (R("etablissements").items || []).map((y) => y.id === id ? Object.assign({}, y, { nom: r["em-n"].trim(), adresse: r["em-a"].trim(), siret: (r["em-s"] || "").replace(/\s/g, ""), horaires_propres: horaires }) : y);
        if (await regler("etablissements", { items: it }, "Établissement modifié.")) dessiner();
      }
      else if (k === "etab-suppr") { if (!await confirmer("Retirer cet établissement ?", "<p>Il disparaît de la liste ; l’historique permet de le remettre.</p>", "Retirer", true)) return; await regler("etablissements", { items: (R("etablissements").items || []).filter((x) => x.id !== id) }); dessiner(); }
      else if (k === "siege") { await regler("etablissements", { items: (R("etablissements").items || []).map((x) => Object.assign({}, x, { siege: x.id === id })) }, "Siège déplacé."); dessiner(); }
      else if (k === "piece-add") { const n = val("#pc-n"), d = val("#pc-d"); if (!n) { dire("Un nom de pièce.", "err"); return; } if (await regler("pieces", { items: (R("pieces").items || []).concat([{ id: "p" + Date.now(), nom: n, exp: d, lien: "" }]) })) { await chargerPage(); dessiner(); } }
      else if (k === "piece-suppr") { const it = (R("pieces").items || []).slice(); it.splice(i, 1); if (await regler("pieces", { items: it })) { await chargerPage(); dessiner(); } }
      else if (k === "iban") { if (S.iban !== undefined) { delete S.iban; dessiner(); return; } const r = await lire("societes.iban_voir", { societe: S.actif }); if (r) { S.iban = r.iban || ""; dessiner(); } else dessiner(); }
      else if (k === "conf") { const c = {}; c[a.dataset.k] = !R("conformite")[a.dataset.k]; await regler("conformite", c); dessiner(); }
      else if (k === "couleur") { await regler("habillage", { accent: a.dataset.c }); dessiner(); }
      else if (k === "entete") { await regler("habillage", { entete: id }); dessiner(); }
      else if (k === "signature") { await regler("habillage", { signature: id }); dessiner(); }
      else if (k === "fn-add") { const n = val("#fn-n"); if (!n) { dire("Un nom pour la fonction.", "err"); return; } if (await geste("societes.fonction_creer", { societe: S.actif, nom: n, partir_de: val("#fn-b") || "membre" }, "Fonction créée. Ajustez ses niveaux dans la grille.")) { await chargerPage(); dessiner(); } }
      else if (k === "cof") { S.cof = id; await chargerCoffre(); dessiner(); }
      else if (k === "cof-ouvrir") { const l = await lire("societes.lister"); const me = (await lire("comptes.moi")) || {}; const compte = me.compte || (me.profil && me.profil.compte) || ""; if (await geste("coffre.espace_creer", { societe: S.actif, nom: nomSoc(), admin: compte }, "Espace de coffre ouvert.")) { await chargerCoffre(); dessiner(); } else if (l) dessiner(); }
      else if (k === "cmode") { const mon = S.espaces.find((x) => x.id === "s:" + S.actif); let url = ""; if (id === "externe") { url = await promptUrl(); if (!url) return; } if (await geste("coffre.regler", { espace: mon.id, mode: id, url: url }, "Mode du coffre réglé.")) { await chargerCoffre(); dessiner(); } }
      else if (k === "cof-accorder") { const u = val("#cm-n"); if (!u) { dire("Tout le monde est déjà membre.", "err"); return; } const r = val("#cm-r"), c = val("#cm-c"); if (await geste("coffre.accorder", { espace: "s:" + S.actif, utilisateur: u, role: r, collections: c === "" ? "" : c, expire: val("#cm-e") }, "Accès donné.")) { await chargerCoffre(); dessiner(); } }
      else if (k === "cof-retirer") { if (!await confirmer("Retirer l’accès de " + a.dataset.c + " ?", "<p>Il ne verra plus ce coffre. Les secrets qu’il a déposés restent.</p>", "Retirer", true)) return; if (await geste("coffre.retirer", { espace: "s:" + S.actif, utilisateur: a.dataset.c }, "Accès retiré.")) { await chargerCoffre(); dessiner(); } }
      else if (k === "rg-reset") { if (await geste("reglages.reinitialiser", { cle: id || a.dataset.k, pour_societe: S.actif }, "Valeur de l’instance rétablie.")) { await chargerPage(); dessiner(); } }
      else if (k === "car-add") { const n = val("#car-n"), e = val("#car-e"); if (!n && !e) { dire("Un nom ou une adresse.", "err"); return; } if (await gesteSoc("contacts.societe_creer", { display_name: n, emails: e ? [e] : [], phone: val("#car-t"), company: val("#car-s") }, "Fiche ajoutée au carnet.")) { await chargerPage(); dessiner(); } }
      else if (k === "car-del") { if (await gesteSoc("contacts.societe_supprimer", { ids: [parseInt(a.dataset.id, 10)] }, "Fiche mise à la corbeille.")) { await chargerPage(); dessiner(); } }
      else if (k === "part-add") { const els = [...(($("#pt-e") || {}).selectedOptions || [])].map((o) => o.value), mode = val("#pt-m"); if (val("#pt-ty") !== "contacts" && mode === "choisis" && !els.length) { dire("Choisissez au moins un utilisateur.", "err"); return; } if (await geste("societes.partager", { source: S.actif, destinataire: val("#pt-d"), type: val("#pt-ty") || "utilisateurs", mode: val("#pt-ty") === "contacts" ? "tous" : mode, elements: els }, "Partage enregistré.")) { await chargerPage(); dessiner(); } }
      else if (k === "part-del") { if (!await confirmer("Retirer ce partage ?", "<p>Les fonctions déjà données restent ; on ne pourra plus en donner à d’autres utilisateurs de cette société.</p>", "Retirer", true)) return; if (await geste("societes.partage_retirer", { source: S.actif, destinataire: a.dataset.d, type: a.dataset.ty || "utilisateurs" }, "Partage retiré.")) { await chargerPage(); dessiner(); } }
      else if (k === "dm-add") { const n = val("#dm-n"), m = val("#dm-m"); if (!n || !m) { dire("Le nom du module et à quoi il servira.", "err"); return; } if (await geste("societes.module_demander", { societe: S.actif, nom: n, motif: m, source: val("#dm-s") }, "Demande envoyée à la société principale.")) { await chargerPage(); dessiner(); } }
      else if (k === "dm-ok") { const mod = ($('[data-dm-mod="' + id + '"]') || {}).value; if (!mod) { dire("Choisissez le module installé à attribuer.", "err"); return; } if (await geste("societes.module_demande_decider", { id: parseInt(id, 10), decision: "accepter", module: mod }, "Module attribué à la société.")) { await chargerPage(); dessiner(); } }
      else if (k === "dm-non") { if (await geste("societes.module_demande_decider", { id: parseInt(id, 10), decision: "refuser" }, "Demande refusée.")) { await chargerPage(); dessiner(); } }
      else if (k === "mod") { if (await geste("societes.module_regler", { societe: S.actif, module: id, ouvert: a.dataset.o !== "1" })) { await chargerPage(); dessiner(); } }
      else if (k === "multi-on") { if (await geste("reglages.regler", { cle: "societes.multi", valeur: true }, "Plusieurs sociétés activées.")) { await chargerBase(); await chargerPage(); dessiner(); } }
      else if (k === "multi-off") { if (S.liste.filter((x) => !x.archivee).length > 1) { dire("Archivez d’abord les autres sociétés.", "err"); return; } if (await geste("reglages.regler", { cle: "societes.multi", valeur: false }, "Retour à une seule société.")) { await chargerBase(); await chargerPage(); dessiner(); } }
      else if (k === "soc-add") { const n = val("#sc-n"), adm = val("#sc-a"); if (!n) { dire("Un nom pour la société.", "err"); return; } const reprise = !!($("#sc-m") && $("#sc-m").checked); if (await geste("societes.creer", { nom: n, administrateur: adm, modules_de: reprise ? "1" : "" }, "Société créée avec ses fonctions et son coffre.")) { await chargerBase(); dessiner(); } }
      else if (k === "archiver") { if (!await confirmer("Archiver cette société ?", "<p>Rien n’est effacé ; elle n’est plus proposée. Elle ne doit plus avoir de comptes.</p>", "Archiver", true)) return; if (await geste("societes.archiver", { societe: id }, "Société archivée.")) { await chargerBase(); dessiner(); } }
      else if (k === "rouvrir") { if (await geste("societes.rouvrir", { societe: id }, "Société rouverte.")) { await chargerBase(); dessiner(); } }
      else if (k === "exporter") {
        const out = { cassandra: "fiche-societe", version: 1, societe: nomSoc(), rubriques: {} };
        ["identite", "siege", "regional", "presence", "etablissements", "horaires", "pieces", "conformite", "habillage"].forEach((r) => { if (S.fiche.rubriques[r]) out.rubriques[r] = S.fiche.rubriques[r]; });
        try { const b = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" }), u = URL.createObjectURL(b), l = document.createElement("a"); l.href = u; l.download = "fiche-" + (nomSoc() || "societe").toLowerCase().replace(/[^a-z0-9]+/g, "-") + ".json"; document.body.appendChild(l); l.click(); l.remove(); setTimeout(() => URL.revokeObjectURL(u), 1000); dire("Fiche exportée.", "ok"); }
        catch (e) { dire("Export impossible dans ce navigateur.", "err"); }
      }
      else if (k === "defaire") { if (await geste("societes.historique_defaire", { societe: S.actif, id: +id }, "Défait.")) { await recharger(); } }
    });
    // La fenêtre se referme AVANT que la promesse ne rende la main : on relève les valeurs saisies au moment du clic, avant sa fermeture.
    async function saisie(titre, corps, oui, ids, danger) {
      const snap = {};
      const h = (ev) => { if (ev.target.closest && ev.target.closest(".kit-m [data-c='oui']")) ids.forEach((id) => { const n = document.getElementById(id); snap[id] = n ? n.value : ""; }); };
      document.addEventListener("click", h, true);
      const ok = await confirmer(titre, corps, oui, danger);
      document.removeEventListener("click", h, true);
      return ok ? snap : null;
    }
    const promptUrl = async () => { const r = await saisie("Adresse du coffre externe", '<input id="so-cf-url" type="url" placeholder="https://coffre.exemple.fr" style="width:100%">', "Enregistrer", ["so-cf-url"]); return r ? (r["so-cf-url"] || "").trim() : ""; };
    racine.addEventListener("change", async (e) => {
      const t = e.target;
      if (t.dataset.r && t.dataset.k) {            // un champ : on enregistre sans redessiner la page (la frappe suivante ne doit pas perdre son champ) ; seuls l'en-tête et l'aperçu se mettent à jour
        const v = {}; v[t.dataset.k] = t.value; const rub = t.dataset.r;
        if (!await regler(rub, v)) { await chargerFiche(); dessiner(); return; }
        majLegere(); }
      else if (t.dataset.h !== undefined) { const j = (R("horaires").jours || []).map((x) => Object.assign({}, x)); j[+t.dataset.h][t.dataset.w] = t.value; if (!await regler("horaires", { jours: j })) await chargerFiche(); dessiner(); }
      else if (t.dataset.rg) {
        const x = (S.regl || []).find((y) => y.cle === t.dataset.rg) || {}, ty = t.dataset.t; let v = t.value;
        if (ty === "booleen") v = t.value === "1"; else if (ty === "entier") v = v === "" ? null : Number(v);
        if (ty === "secret") { if (v === "***") return; if (await geste("reglages.regler_secret", { cle: x.cle, valeur: v, pour_societe: S.actif }, "Réglage enregistré.")) await chargerPage(); }
        else if (await geste("reglages.regler", { cle: x.cle, valeur: v, pour_societe: S.actif }, "Réglage enregistré.")) await chargerPage();
        dessiner(); }
      else if (t.dataset.role) { const v = {}; v[t.dataset.role] = t.value; await regler("roles", v); dessiner(); }
      else if (t.dataset.fc) { const p = t.dataset.fc.split("|"), n = +t.value, d = DOMAINES.find((x) => x[0] === p[1]); if (n === 3 && d && d[2] && !await confirmer("Droit sensible", "<p>« Gérer » « " + esc(d[1]) + " » donne accès à des gestes sensibles ; chaque usage sera journalisé.</p>", "Accorder", true)) { await chargerPage(); dessiner(); return; } if (await geste("societes.fonction_regler", { societe: S.actif, fonction: p[0], domaine: p[1], niveau: n })) await chargerPage(); dessiner(); }
      else if (t.dataset.af !== undefined) { if (await geste("societes.affecter", { societe: S.actif, utilisateur: t.dataset.af, fonction: t.value }, "Fonction donnée.")) await chargerPage(); dessiner(); }
      else if (t.dataset.cm) { const m = ((S.cofMembres && S.cofMembres.membres) || []).find((x) => x.compte === t.dataset.cm) || {}; if (await geste("coffre.accorder", { espace: "s:" + S.actif, utilisateur: t.dataset.cm, role: t.value, collections: t.value === "admin" ? (m.collections || "") : (m.collections || "*"), expire: m.expire || "" }, "Rôle changé.")) await chargerCoffre(); dessiner(); }
      else if (t.id === "so-imp") {
        const f = t.files && t.files[0]; t.value = ""; if (!f) return;
        let d; try { d = JSON.parse(await f.text()); } catch (er) { dire("Ce fichier n’est pas une fiche : JSON illisible.", "err"); return; }
        if (!d || d.cassandra !== "fiche-societe" || !d.rubriques) { dire("Ce fichier n’est pas une fiche de société.", "err"); return; }
        const noms = Object.keys(d.rubriques).filter((r) => ["identite", "siege", "regional", "presence", "etablissements", "horaires", "pieces", "conformite", "habillage"].indexOf(r) >= 0);
        if (!noms.length) { dire("Aucune rubrique à importer.", "err"); return; }
        if (!await confirmer("Importer cette fiche ?", "<p>Elle remplace les rubriques suivantes de <b>" + esc(nomSoc()) + "</b> (chacune se défait depuis l’historique) :</p><ul>" + noms.map((r) => "<li>" + esc(r) + "</li>").join("") + "</ul>", "Importer")) return;
        let bon = 0; for (const r of noms) { const v = Object.assign({}, d.rubriques[r]); if (await regler(r, v)) bon++; }
        dire(bon + " rubrique(s) importée(s).", bon === noms.length ? "ok" : "err"); await recharger();
      }
      else if (t.id === "sm-j" || t.id === "sm-h") { S.sim.jour = +$("#sm-j").value; S.sim.heure = +(($("#sm-h").value || "10:00").slice(0, 2)); dessiner(); }
    });
    racine.addEventListener("input", (e) => {                       // l’aperçu bouge à chaque frappe ; la fiche s’enregistre à la validation du champ
      const t = e.target; if (!t.dataset.r || !t.dataset.k || t.tagName !== "INPUT") return;
      const rub = S.fiche.rubriques[t.dataset.r]; if (!rub) return; rub[t.dataset.k] = t.value;
      const pv = $("#so-pv"); if (pv) pv.innerHTML = apercu();
      if (t.dataset.k === "siren") { const h = $("#h-siren"), ok = luhn(t.value); t.classList.toggle("bad", !!t.value && !ok); if (h) { h.className = "hint " + (!t.value ? "" : (ok ? "ok" : "ko")); h.textContent = !t.value ? "9 chiffres. Le contrôle est local, rien n’est envoyé." : (ok ? "Valide · TVA " + tva(t.value) : "Clé de contrôle invalide : vérifiez le numéro."); } }
    });
    // Rouvrir l'écran depuis le menu repart de sa page d'origine, avec des données fraîches
    const initiale = S.page, onglet = corps.closest(".tab-content");
    if (onglet) { let etait = onglet.classList.contains("active");
      new MutationObserver(() => { const actif = onglet.classList.contains("active"); if (actif && !etait && !S.charge) { S.page = initiale; S.iban = undefined; recharger(); } etait = actif; }).observe(onglet, { attributes: true, attributeFilter: ["class"] }); }
    dessiner();
    await chargerBase(); await chargerFiche(); await chargerPage(); S.charge = false; dessiner();
  };
})();
// ▲▲▲ FIN BORNE CN ▲▲▲

// ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
// CN : tout ce fichier est du nexus : à compléter
// EC : néant (aucun point d'évolution déclaré pour l'instant)
// LIEN : à compléter (contrat, fichiers voisins)
